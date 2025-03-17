"""Top-level package for indiapins."""

import bz2
import json
import os
import re
import sys

__author__ = "Pawan Kumar Jain"
__email__ = "pawanjain.432@gmail.com"
__version__ = "1.0.4"

print(">>> Loading indiapins from:", __file__)

_valid_zipcode_length = 6
_digits = re.compile(r"[^\d]")

# Ensure Python 3
if sys.version_info < (3, 0):
    raise TypeError("Indiapins is supported only on Python 3.")
else:
    bz2_open = bz2.open


def _clean_zipcode(fn):
    """Decorator that ensures the argument is a 6-digit numeric string."""
    def decorator(zipcode, *args, **kwargs):
        if not zipcode or not isinstance(zipcode, str):
            raise TypeError("Invalid type, pincode must be a string.")
        return fn(_clean(zipcode), *args, **kwargs)
    return decorator


def _clean(zipcode):
    if len(zipcode) != _valid_zipcode_length:
        raise ValueError("Invalid format, pincode must be exactly 6 digits.")
    if bool(_digits.search(zipcode)):
        raise ValueError("Invalid characters, pincode may only contain digits.")
    return zipcode


def _resource_path(relative_path):
    """Construct an absolute path to our resource."""
    try:
        # PyInstaller sets sys._MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ---------------------------------------------------------
# Load the data from pins.json.bz2, skipping bad lines
# ---------------------------------------------------------

_zips_json = _resource_path(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "pins.json.bz2")
)

_zips = []
print(">>> Attempting to load data from:", _zips_json)

try:
    with bz2_open(_zips_json, "rt") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                # Skip empty lines
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # Skip malformed JSON lines
                continue

            # Must be a dict and contain "Pincode"
            if not isinstance(obj, dict):
                continue
            if "Pincode" not in obj:
                continue

            # Now it's good; add it to our list
            _zips.append(obj)
except Exception as e:
    print(f"ERROR: Could not load pinned data. {type(e).__name__}: {e}")

print(f">>> Done loading. Total valid records: {len(_zips)}")


# ---------------------------------------------------------
# Core Functions
# ---------------------------------------------------------

@_clean_zipcode
def matching(zipcode, zips=None):
    """
    Return all records that match the given pincode.
    Because we only store dicts that contain 'Pincode',
    we can safely check it, but we still do a final check 
    that 'Pincode' is in each dict.
    """
    if zips is None:
        zips = _zips

    results = []
    for entry in zips:
        if "Pincode" not in entry:
            # Shouldn't happen if we loaded properly, but let's be safe
            continue
        # Compare as string to handle int vs str
        if str(entry["Pincode"]) == zipcode:
            results.append(entry)
    return results


@_clean_zipcode
def isvalid(zipcode, zips=None):
    """Return True if the pincode exists in our dataset, else False."""
    if zips is None:
        zips = _zips
    return bool(matching(zipcode, zips=zips))


@_clean_zipcode
def districtmatch(zipcode, zips=None):
    """Return a comma-separated string of distinct District names for the pincode."""
    if zips is None:
        zips = _zips

    districts = set()
    for entry in zips:
        if "Pincode" in entry and str(entry["Pincode"]) == zipcode:
            dist = entry.get("District")
            if dist:
                districts.add(dist)

    if not districts:
        raise ValueError("Invalid Pincode, not found in database")
    return ", ".join(districts)


@_clean_zipcode
def coordinates(zipcode, zips=None):
    """Return a dict {Name: {latitude, longitude}} for each matching entry."""
    if zips is None:
        zips = _zips

    matches = matching(zipcode, zips=zips)
    coords_map = {}
    for entry in matches:
        # Use get() so we don't blow up if key missing
        name = entry.get("Name", "Unknown")
        lat = entry.get("Latitude", "")
        lon = entry.get("Longitude", "")
        coords_map[name] = {
            "latitude": str(lat),
            "longitude": str(lon),
        }
    return coords_map

@_clean_zipcode
def nearby(zipcode, max_diff=0.05, zips=None):
    """
    Return a list of pincodes that are 'near' the given pincode,
    using a simple difference in lat + long as a distance metric.

    :param zipcode: The 6-digit reference pincode (string).
    :param max_diff: Numeric threshold to decide 'how far'. 
                     0.05 is an arbitrary default range that you can adjust.
                     The higher this value, the more pincodes you get.
    :param zips:    Optional list of pincode dicts to search. Defaults to _zips.
    :return:        A list of distinct pincodes (strings) that qualify as 'nearby'.
    """

    if zips is None:
        zips = _zips  # references your global data loaded from pins.json.bz2

    # 1) Gather all lat/lon for the reference pincode:
    center_entries = [z for z in zips 
                      if "Pincode" in z and str(z["Pincode"]) == zipcode
                         and z.get("Latitude") and z.get("Longitude")]
    if not center_entries:
        return []  # No valid lat/lon for this reference pincode in the dataset

    # For pincodes that appear multiple times, pick the first or average lat/lon:
    # Here, let's just pick the first record
    center_lat = float(center_entries[0]["Latitude"])
    center_lon = float(center_entries[0]["Longitude"])

    nearby_pins = set()

    # 2) Compare every record’s lat/lon to the center:
    for record in zips:
        if "Pincode" not in record:
            continue
        # Must have numeric lat/long:
        try:
            lat = float(record.get("Latitude", ""))
            lon = float(record.get("Longitude", ""))
        except ValueError:
            # skip if lat/lon is missing or not convertible
            continue

        # Example "distance" measure: sum of absolute diffs in lat and lon
        dist = abs(lat - center_lat) + abs(lon - center_lon)

        if dist <= max_diff:
            # It's "near" the center by this simplistic measure
            nearby_pins.add(str(record["Pincode"]))

    # 3) Remove the center pincode itself if you only want “others”
    # If you want to include the center pincode in the result, skip this step
    if zipcode in nearby_pins:
        nearby_pins.remove(zipcode)

    return sorted(nearby_pins)
