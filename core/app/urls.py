
from django.urls import path, re_path
from . import views

urlpatterns = [
    # Matches any html file - to be used for gentella
    # Avoid using your .html in your resources.
    # Or create a separate django app.
   # The home page
    path('', views.index, name='home'),
    path('inspections',views.inspections,name='inspections'),
    path('all',views.allPD,name='all'),
    path('allPD',views.allPD,name='allPD'),
    path('levelPics',views.levelPics,name='levelPics'),
    path('level', views.level, name='level'),
    path('test',views.testPage, name='testpage'),
    path('importWMS',views.importWMS,name='importWMS')
]
