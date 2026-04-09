from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('user', 'User'),
    )
    
    name = models.CharField(max_length=255, blank=True, null=True)
    position = models.CharField(max_length=255, blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    
    class Meta:
        db_table = 'users'
    
    # email is already in AbstractUser, but we can make it optional if needed
    # username and password are also in AbstractUser
    
    def __str__(self):
        return self.username
