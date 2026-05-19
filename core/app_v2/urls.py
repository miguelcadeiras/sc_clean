from django.urls import path

from app import views as legacy_views
from . import views

urlpatterns = [
    path('all', views.all_vr_no_pd_v2, name='all_v2'),
    path('levelPics', views.level_pics_v2, name='level_pics_v2'),
    path('readedAnalysis', legacy_views.readedAnalysisVR_noPD, name='readed_analysis_v2'),
]
