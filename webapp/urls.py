from django.urls import path
from assess import views
urlpatterns = [path("", views.form, name="form"), path("report/<int:pk>/", views.report, name="report")]
