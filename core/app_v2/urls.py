from django.urls import path

from . import views

urlpatterns = [
    path('all', views.all_vr_no_pd_v2, name='all_v2'),
]
