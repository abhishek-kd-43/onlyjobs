#!/usr/bin/env python3
"""
OnlyJobs — One-Click Scraper
Run this file from Terminal:
    python3 scrape_now.py

Or double-click this file in Finder (if Python is set as default).
Data will be saved to data.json in the same folder.
"""

import os
import sys

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

try:
    from scraper import main
    main()
except ImportError as e:
    print(f"\n❌ Missing dependency: {e}")
    print("\nInstall required packages with:")
    print("  pip3 install requests beautifulsoup4")
    sys.exit(1)
except KeyboardInterrupt:
    print("\n\n⚠️  Scraping cancelled by user.")
    sys.exit(0)
