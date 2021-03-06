from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import *
from django.contrib.auth import logout, authenticate, login

from rest_framework.authtoken.models import Token
from rest_framework import generics, status
from rest_framework.authentication import TokenAuthentication

import datetime
import json

from .serializers import *

def home(request):
    return render(request, 'index.html')

def harp(request):
    return render(request, 'harp.html')

def datadetails(request):
    return render(request, 'datadetails.html')

class SaveData(generics.GenericAPIView):
    permission_classes = (AllowAny, )

    def post(self, request, *args, **kwargs):
        try:
            form_data = (request.body.decode()).split('Token')
            num = 0
            numbers = []
            for char in form_data[0]+'$':
                if char.isdigit():
                    num = num * 10 + int(char)
                else:
                    numbers.append(num)
                    num = 0

            Data.objects.create(
                aqi=numbers[0]/100,
                ldr=numbers[1],
                hits=numbers[2],
                road=Token.objects.get(key=form_data[1]).user,
            )

            return JsonResponse({}, status=status.HTTP_200_OK)
        except Exception as e:
            return JsonResponse({'error': str(e), 'body': request.body.decode(), 'numbers': numbers, 'token': form_data[1]}, status=status.HTTP_200_OK)


class GetData(generics.GenericAPIView):
    permission_classes = (AllowAny,)

    def get(self, request, *args, **kwargs):
        latitude = int(float(kwargs['latitude'])*1000000)
        longitude = int(float(kwargs['longitude'])*1000000)

        sensors = Sensor.objects.all()

        min = {'sensor': None, 'dist': None}
        for sensor in sensors:
            lat_diff = sensor.latitude - latitude
            long_diff = sensor.longitude - longitude
            dist = lat_diff * lat_diff + long_diff * long_diff
            if (not min['dist'] or dist < min['dist']) and dist<5000000:
                min['sensor'] = sensor
                min['dist'] = dist

        if min['sensor']:
            road = min['sensor'].road
            data = Data.objects.filter(road=road)
            return JsonResponse({'data': DataSerializer(data, many=True).data, 'road': RoadSerializer(road).data, 'sensor': str(min['sensor']), 'dist': min['dist']}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'data': []}, status=status.HTTP_200_OK)


class GetGeoJson(generics.GenericAPIView):
    permission_classes = (AllowAny, )

    def get(self, request, *args, **kwargs):

        latitude = int(float(kwargs['latitude'])*1000000)
        longitude = int(float(kwargs['longitude'])*1000000)

        GeoJson = {
            "type": "FeatureCollection",
            "features": []
        }

        sensors = Sensor.objects.filter(latitude__lte=latitude+2000000, latitude__gte=latitude-2000000,
                              longitude__lte=longitude+2000000, longitude__gte=longitude-2000000).order_by('id')
        roads = []
        for sensor in sensors:
            data = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [ sensor.longitude/1000000, sensor.latitude/1000000, 0.0 ]
                }
            }
            GeoJson['features'].append(data)
            if not sensor.road in roads:
                roads.append(sensor.road)

        for road in roads:
            data = {
                "type": "line",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[ sensor.longitude/1000000, sensor.latitude/1000000 ] for sensor in road.sensor_set.all().order_by('id')]
                }
            }
            GeoJson['features'].append(data)

        return JsonResponse(GeoJson, status=status.HTTP_200_OK)


class NewRoad(generics.GenericAPIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        form_data = json.loads(request.body.decode())
        try:
            lane_count = form_data['lane_count']
            sensors = form_data['sensors']
        except:
            lane_count = None
            sensors = []

        try:
            username = form_data['username']
            password = form_data['password']
            two_way = form_data['2way']

            for sensor in sensors:
                if Sensor.objects.filter(latitude=sensor['latitude'],longitude=sensor['longitude']).exists():
                    raise Exception("Sensor already exists")

            road = Road.objects.create(
                username=username,
                password=password,
                lane_count=lane_count,
                two_way=two_way,
                first_name=' '.join(username.split(' ')[:-1]),
                last_name=username.split(' ')[-1]
            )
            road.set_password(password)
            road.save()

            login(request, road)

            for sensor in sensors:
                Sensor.objects.create(
                latitude=int(float(sensor['latitude'])*1000000),
                longitude=int(float(sensor['longitude'])*1000000),
                road=road
                )

            token, _ = Token.objects.get_or_create(user=road)

            response_data = {
                'token': token.key,
            }
            return JsonResponse(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            response_data = {'error_message': "Cannot sign you up due to " + str(e)}
            return JsonResponse(response_data, status=status.HTTP_400_BAD_REQUEST)
