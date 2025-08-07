from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class TMDBContactUtils(models.AbstractModel):
    _name = "tmdb.utils.contact"
    _description = "TMDB Contact Utilities"

    # De entrada tenemos: director_name
    def find_or_create_director_contact_simple(self, director_name, profile_path=None):
        if not director_name:
            return None

        try:
            # Buscar director existente (QUERY EN RES PARTNER >> name=director_name AND is_director=True)
            existing_contact = self.env["res.partner"].search(
                [("name", "=", director_name), ("is_director", "=", True)],
                limit=1,
            )

            if existing_contact:
                # Update image if we have a profile_path and the contact doesn't have an image yet
                if profile_path and not existing_contact.image_1920:
                    existing_contact.update_image_from_tmdb_profile(profile_path)
                return existing_contact

            # Creamos nuevo director si no existe el contacto
            contact_vals = {
                "name": director_name,
                "is_company": False,
                "is_director": True,  # Nuevo campo
                "function": "Film Director",  # Function aka Job Description
            }

            director_contact = self.env["res.partner"].create(contact_vals)

            # Add profile image if available
            if profile_path:
                director_contact.update_image_from_tmdb_profile(profile_path)

            return director_contact

        except Exception as e:
            _logger.error(f"Error creating director contact for {director_name}: {e}")
            return None

    def find_or_create_director_contact(self, director_name, profile_path=None):
        """Find existing director contact or create a new one"""
        if not director_name:
            return None

        # Validate contact creation
        if not self._validate_contact_creation(director_name):
            return None

        try:
            # Search for existing contact with the same name
            existing_contact = self.env["res.partner"].search(
                [("name", "=", director_name), ("is_company", "=", False)], limit=1
            )

            if existing_contact:
                # Asegurar que el contacto existente esté marcado como director
                if not existing_contact.is_director:
                    existing_contact.write({"is_director": True})
                # Update image if we have a profile_path and the contact doesn't have an image yet
                if profile_path and not existing_contact.image_1920:
                    existing_contact.update_image_from_tmdb_profile(profile_path)
                return existing_contact

            # Create new director contact with safe field handling
            contact_vals = {
                "name": director_name,
                "is_company": False,
                "is_director": True,  # ← AGREGADO: Marcar como director
            }

            # Add function field if it exists (contacts module)
            if hasattr(self.env["res.partner"], "function"):
                contact_vals["function"] = "Film Director"

            # Add category_id field if it exists (this is the correct field name)
            if hasattr(self.env["res.partner"], "category_id"):
                contact_vals["category_id"] = [
                    (6, 0, self._get_director_category_ids())
                ]

            # Try alternative category field names as fallback
            if "category_id" not in contact_vals:
                category_field = self._get_available_category_field()
                if category_field and category_field != "category_id":
                    contact_vals[category_field] = [
                        (6, 0, self._get_director_category_ids())
                    ]

            director_contact = self.env["res.partner"].create(contact_vals)

            # Add profile image if available
            if profile_path:
                director_contact.update_image_from_tmdb_profile(profile_path)

            return director_contact

        except Exception as e:
            _logger.error(f"Error creating director contact for {director_name}: {e}")
            _logger.info("Trying simple contact creation without categories...")
            # Fallback to simple contact creation without categories
            return self.find_or_create_director_contact_simple(
                director_name, profile_path
            )

    def _validate_contact_creation(self, director_name):
        """Validate if we can create a contact for this director"""
        # Check if user has permission to create contacts
        if not self.env["res.partner"].check_access_rights(
            "create", raise_exception=False
        ):
            _logger.warning(
                f"User doesn't have permission to create contacts for director: {director_name}"
            )
            return False

        # Check if director name is valid
        if not director_name or len(director_name.strip()) < 2:
            _logger.warning(f"Invalid director name: {director_name}")
            return False

        return True

    def _get_available_category_field(self):
        """Get the available category field name on res.partner"""
        partner_model = self.env["res.partner"]

        # Check for different possible category field names
        category_fields = [
            "category_id",
            "category_ids",
            "categories",
            "tag_ids",
            "tags",
        ]

        for field_name in category_fields:
            if hasattr(partner_model, field_name):
                return field_name

        return None

    def _get_director_category_ids(self):
        """Get or create director category IDs"""
        try:
            # Check if res.partner.category model exists
            if not hasattr(self.env, "res.partner.category"):
                _logger.warning("res.partner.category model not available")
                return []

            director_category = self.env["res.partner.category"].search(
                [("name", "=", "Film Director")], limit=1
            )

            if not director_category:
                director_category = self.env["res.partner.category"].create(
                    {
                        "name": "Film Director",
                        "color": 1,  # Red color
                    }
                )

            return [director_category.id]
        except Exception as e:
            _logger.error(f"Error creating director category: {e}")
            return []

    def sync_all_directors_to_contacts(self, movie_records):
        """Sync all directors from movies to contacts"""
        movies_with_directors = movie_records.search(
            [
                ("director", "!=", False),
                ("director", "!=", ""),
                ("director_id", "=", False),
            ]
        )

        synced_count = 0
        for movie in movies_with_directors:
            try:
                director_contact = self.find_or_create_director_contact(movie.director)
                if director_contact:
                    movie.write({"director_id": director_contact.id})
                    synced_count += 1
            except Exception as e:
                _logger.error(
                    f"Error syncing director {movie.director} for movie {movie.title}: {e}"
                )

        return synced_count

    def create_director_contact_from_field(self, movie_record):
        """Create director contact from the director field"""
        if not movie_record.director:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Error",
                    "message": "No director name available to create contact.",
                    "type": "danger",
                },
            }

        try:
            director_contact = self.find_or_create_director_contact(
                movie_record.director
            )
            if director_contact:
                movie_record.write({"director_id": director_contact.id})
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": "Success",
                        "message": f"Created contact for director: {movie_record.director}",
                        "type": "success",
                    },
                }
            else:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": "Error",
                        "message": "Failed to create director contact.",
                        "type": "danger",
                    },
                }
        except Exception as e:
            _logger.error(
                f"Error creating director contact for {movie_record.director}: {e}"
            )
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Error",
                    "message": f"An error occurred: {str(e)}",
                    "type": "danger",
                },
            }
