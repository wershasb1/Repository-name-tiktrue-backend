"""
Integration tests for model downloader encryption functionality
Tests encryption integration with model downloader
"""

import unittest
import tempfile
import shutil
import json
import os
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path
from datetime import datetime

from models.model_downloader import ModelDownloader, ModelInfo, ModelTier
from models.model_encryption import ModelEncryption, create_model_encryption
from security.license_validator import SubscriptionTier, License