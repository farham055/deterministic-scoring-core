from django.db import models
class Assessment(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    declaration = models.CharField(max_length=16)
    scenario_json = models.TextField()
    result_json = models.TextField()
