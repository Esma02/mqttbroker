from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class BrokerConnection(models.Model):
    broker_ip = models.CharField(max_length=255)
    port = models.IntegerField()
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    topic = models.CharField(max_length=255)

class DynamicTable(models.Model):
    table_name = models.CharField(max_length=255)

    def __str__(self):
        return self.table_name

class TableInfo(models.Model):
    broker_connection = models.ForeignKey(BrokerConnection, on_delete=models.CASCADE, related_name='tables')  # Broker bağlantısı
    table_name = models.CharField(max_length=255)  # Tablo adı
    created_at = models.DateTimeField(default=timezone.now)  # Tablonun oluşturulma tarihi

    def __str__(self):
        return self.table_name

class TableData(models.Model):
    table_info = models.ForeignKey(TableInfo, on_delete=models.CASCADE, related_name='data_entries')  # İlişkili tablo bilgisi
    data = models.JSONField()                      # API'den alınan veriler, JSON formatında
    

