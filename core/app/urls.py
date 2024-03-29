
from django.urls import path, re_path,include
from . import views
from django.contrib.auth import views as auth_views



urlpatterns = [
    # Matches any html file - to be used for gentella
    # Avoid using your .html in your resources.
    # Or create a separate django app.
   # The home page
    path('', views.index, name='home'),
    path('inspections',views.inspections,name='inspections'),
    path('all_old_1',views.allVR_noPD,name='all_old'),
    path('all',views.allVR_noPD_1,name='all'), ## ESTA ES LA CORRECTA
    # path('all', views.allVR_noPD_348, name='348'),  ## PSEUDO INTENTO DE SALVATAJE POR ERROR ENCODER.

    # path('allPD',views.allPD,name='allPD'),
    path('allPDvr', views.allPDvr, name='allPDvr'),
    path('allVR_noPD', views.allVR_noPD, name='allVR_noPD'),

    # path('no_match',views.no_match,name='no_match'),

    path('levelPics',views.levelPics,name='levelPics'),
    path('carrousel', views.carrousel, name='carrousel'),
    path('level', views.level, name='level'),
    path('test',views.testPage, name='testpage'),
    path('importWMS',views.importWMS,name='importWMS'),
    # path('readedAnalysis', views.readedAnalysis, name='readedAnalysis'),
    path('readedAnalysis', views.readedAnalysisVR_noPD, name='readedAnalysis'),
    path('readedAnalysisVR', views.readedAnalysisVR_noPD, name='readedAnalysisVR'),

    path('plusMinus', views.plusMinus, name='plusMinus'),

    path("password-reset",
         auth_views.PasswordResetView.as_view(template_name="registration/password_reset.html"),
         name="password_reset"),
    path("password-reset/done/",
         auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"),
         name="password_reset_done"),
    path("password-reset-confirm/<uidb64>/<token>",
         auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"),
         name="password_reset_confirm"),
    path("password-reset-complete/",
         auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"),
         name="password_reset_complete"),
    path('status', views.status, name='status'),
    path('status_ajax', views.status_ajax, name='status_ajax'),

    path('devices', views.devices, name='devices') ,

]
