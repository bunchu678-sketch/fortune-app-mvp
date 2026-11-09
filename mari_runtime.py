"""Identify the dedicated release without changing ordinary doctor/admin defaults."""
import os
from pathlib import Path

TEACHER_SURFACE = 'teacher'
RELEASE_MARKER = Path(__file__).with_name('.mari-reading-release')


def runtime_configuration():
    surface = os.environ.get('FORTUNE_DEPLOYMENT_SURFACE', '')
    profile = os.environ.get('FORTUNE_READING_ACCESS_PROFILE', '')
    selected = os.environ.get('FORTUNE_READING_ALLOWED_USER_IDS', '')
    required = os.environ.get('FORTUNE_REQUIRED_DEPLOYMENT_SURFACE', '')
    marked = RELEASE_MARKER.exists() or RELEASE_MARKER.is_symlink()
    if marked:
        try:
            if RELEASE_MARKER.is_symlink() or RELEASE_MARKER.read_text(encoding='utf-8') != TEACHER_SURFACE+'\n':
                raise ValueError()
        except (OSError, ValueError):
            raise ValueError('dedicated_release_marker_invalid') from None
    strict = marked or bool(required) or surface == 'teacher' or (not surface and bool(profile or selected))
    if not strict:
        if surface not in ('', 'combined', 'admin'):
            raise ValueError('deployment_surface_invalid')
        return surface or 'combined'
    if surface != 'teacher' or required not in ('', TEACHER_SURFACE):
        raise ValueError('dedicated_reading_configuration_required')
    if profile or selected or os.environ.get('FORTUNE_READING_REQUIRED_PROFILE'):
        raise ValueError('obsolete_fixed_reader_configuration')
    return 'teacher'
