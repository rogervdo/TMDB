{
    "name": "Roger's Movies Module",
    "version": "18.0.1.0.0",
    "category": "Customizations",
    "summary": "Custom Addon for Odoo 18",
    "description": """
        Custom Addon Module for Odoo 18
        ===============================
        
        This module provides TMDB API integration for movie data.
        
        Features:
        - TMDB API integration
        - Movie data synchronization
        - Configuration management
        - Bulk sync operations
        - Collection analysis tools
        - Permanent analysis storage
    """,
    "author": "Roger Villarreal",
    "website": "https://www.hanova.consulting",
    "depends": [
        "base",
        "web",
        "contacts",
    ],
    "external_dependencies": {
        "python": ["requests"],
    },
    "data": [
        "views/res_config_settings_views.xml",
        "views/res_partner_views.xml",
        "views/tmdb_movie_views.xml",
        "views/tmdb_movie_search_filters.xml",
        "views/tmdb_genre_views.xml",
        "views/tmdb_sync_wizard_views.xml",
        "views/tmdb_movie_search_wizard_views.xml",
        "views/tmdb_collection_analysis_wizard_views.xml",
        "views/tmdb_permanent_analysis_views.xml",
        "views/tmdb_search_result_views.xml",
        "views/tmdb_data_cleanup_wizard_views.xml",
        "security/ir.model.access.csv",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
