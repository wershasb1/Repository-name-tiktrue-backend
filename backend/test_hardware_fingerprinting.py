#!/usr/bin/env python3
"""
Test script for Hardware Fingerprinting functionality
Tests the hardware fingerprint generation, validation, and license binding
"""

import os
import sys
import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tiktrue_backend.settings')
os.environ.setdefault('DEBUG', 'True')
django.setup()

# Add testserver to ALLOWED_HOSTS for testing
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')

from django.test import TestCase, Client
from django.contr