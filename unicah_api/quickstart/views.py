from django.shortcuts import render
from django.contrib.auth.models import User, Group
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_jwt.authentication import JSONWebTokenAuthentication
from django.http import JsonResponse
from django.forms.models import model_to_dict

class GradecheckEndpoint(APIView):
    """
    API endpoint that allows users to be viewed or edited.
    """
    toReturn = {}
    toReturn['works']  = True
    return JsonResponse(toReturn.__dict__, safe=False)

# Create your views here.
