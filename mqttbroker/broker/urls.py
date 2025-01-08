from django import views
from django.urls import path
from .views import use_custom_database,create_database,index,CreateTable,ShowTableData,StartBrokerConnection,StopBrokerConnection,FilterTableData,GetColumns,TopcListView
from .import views 

urlpatterns = [
    path('',views.index,name='index'),
    path('create_table/',CreateTable.as_view(),name='create_table'),
    path('show_table_data/',ShowTableData.as_view(),name='show_table_data'),
    path('start_broker_connection/', StartBrokerConnection.as_view(), name='start_broker_connection'),
    path('stop_broker_connection/', StopBrokerConnection.as_view(), name='stop_broker_connection'),
    path('filter_table/', FilterTableData.as_view(), name='filter_table'),
    path('apply_filter/',FilterTableData.as_view(),name="apply_filter"),
    path('get_columns/<str:table_name>/', GetColumns.as_view(), name='get_columns'),
    path('topic_list/',TopcListView.as_view(),name='topic_list'),
    path('create_database',views.create_database,name='create_database'),
    path('use-database/',views.use_custom_database,name='use_custom_database')


    
]