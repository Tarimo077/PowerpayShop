from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('mark_read/<int:notif_id>/', views.mark_read, name='mark_read'),
    path('read_all/', views.mark_all_as_read, name='read_all'),
    path('dropdown/', views.dropdown, name='dropdown'),  
    path('unread_count/', views.unread_count, name='unread_count'),
]
