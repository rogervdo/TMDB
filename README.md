# TMDB Movies Module - Odoo 18

This module provides TMDB API integration for movie data management in Odoo 18.

## Features

- **TMDB API Integration**: Sync movie data from The Movie Database
- **Movie Management**: Store and manage movie information locally
- **Search Functionality**: Search movies both locally and on TMDB
- **Data Cleanup Tools**: Detect duplicates and incomplete information
- **Collection Analysis**: Analyze movie collections and generate reports
- **Configuration Management**: Easy setup and configuration

## Data Cleanup Wizard

The Data Cleanup Wizard helps identify and report data quality issues in your movie database:

### Duplicate Detection

- **TMDB ID**: Find movies with duplicate TMDB IDs
- **Title**: Find movies with duplicate titles (case-insensitive)
- **Title + Release Date**: Find movies with same title and release date
- **All Criteria**: Combine all duplicate detection methods

### Incomplete Information Detection

- **Basic Information**: Check for missing title, overview, and release date
- **Extended Information**: Check for missing director, genres, and poster
- **All Information**: Comprehensive check of all important fields

### Features

- **Non-destructive**: Only reports issues, doesn't modify data
- **Configurable**: Choose which types of analysis to run
- **Detailed Reports**: View specific movies with issues
- **Export Capabilities**: Generate reports for further analysis

### Usage

1. Navigate to **Movies > Data Cleanup** in the main menu
2. Select the types of analysis you want to run
3. Choose detection criteria for duplicates and incomplete information
4. Click **"Run Analysis"** to start the scan
5. Review results and use the action buttons to view details
6. Export reports for further analysis if needed

## Module Structure

## Module Structure

```
custom_addon/
├── __init__.py
├── __manifest__.py
├── models/
│   └── __init__.py
├── views/
│   └── (add your view files here)
├── security/
│   └── ir.model.access.csv
├── data/
│   └── (add your data files here)
├── demo/
│   └── (add your demo files here)
├── wizard/
│   └── __init__.py
├── report/
│   └── __init__.py
├── tests/
│   └── __init__.py
├── static/
│   └── description/
│       └── icon.png
└── README.md
```

## Getting Started

1. Rename the module folder to your desired module name
2. Update the `__manifest__.py` file with your module details
3. Add your models in the `models/` directory
4. Create views in the `views/` directory
5. Update security rights in `security/ir.model.access.csv`
6. Add any data files in `data/` or `demo/` directories

## Installation

1. Copy this module to your Odoo addons directory
2. Update the addons list in Odoo
3. Install your module from the Apps menu

## License

This template is licensed under LGPL-3.

