# forms.py
from django import forms

class DateRangeForm(forms.Form):
    start_date = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    end_date = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    filter_column = forms.CharField(max_length=100)  # Filtrelenecek kolonun adı