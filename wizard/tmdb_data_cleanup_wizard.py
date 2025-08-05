from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class TMDBDataCleanupWizard(models.TransientModel):
    _name = "tmdb.data.cleanup.wizard"
    _description = "TMDB Data Cleanup Wizard"

    # Detection criteria
    detection_criteria = fields.Selection(
        [
            ("tmdb_id", "Duplicate TMDB IDs"),
            ("title_date", "Same Title and Release Date"),
            ("title_similar", "Similar Titles (same year)"),
            ("all", "All Criteria"),
        ],
        string="Detection Criteria",
        required=True,
        default="tmdb_id",
        help="Choose criteria for detecting duplicate movies",
    )

    # Action options
    action_type = fields.Selection(
        [
            ("merge", "Merge Duplicates"),
            ("delete", "Delete Duplicates"),
        ],
        string="Processing Action",
        required=True,
        default="merge",
        help="Choose what action to take on duplicates",
    )

    # Merge preferences
    keep_preference = fields.Selection(
        [
            ("newest", "Keep Newest Record"),
            ("most_complete", "Keep Most Complete Record"),
            ("highest_rating", "Keep Highest Rated"),
            ("manual", "Manual Selection"),
        ],
        string="Keep Preference",
        default="most_complete",
        help="Which record to keep when merging duplicates",
    )

    # Results
    duplicate_count = fields.Integer(string="Duplicates Found", readonly=True)
    processed_count = fields.Integer(string="Records Processed", readonly=True)

    # Analysis results
    analysis_results = fields.Text(string="Analysis Results", readonly=True)

    # Duplicate movie lines for detailed view
    duplicate_line_ids = fields.One2many(
        "tmdb.data.cleanup.wizard.line",
        "wizard_id",
        string="Duplicate Movies",
        readonly=True,
    )

    def action_detect_duplicates(self):
        """Detect duplicate movies based on selected criteria"""
        self.ensure_one()

        duplicates = []
        analysis_text = []

        if self.detection_criteria in ["tmdb_id", "all"]:
            tmdb_duplicates = self._find_tmdb_id_duplicates()
            duplicates.extend(tmdb_duplicates)
            analysis_text.append(f"TMDB ID duplicates: {len(tmdb_duplicates)} groups")

        if self.detection_criteria in ["title_date", "all"]:
            title_date_duplicates = self._find_title_date_duplicates()
            duplicates.extend(title_date_duplicates)
            analysis_text.append(
                f"Title+Date duplicates: {len(title_date_duplicates)} groups"
            )

        if self.detection_criteria in ["title_similar", "all"]:
            similar_title_duplicates = self._find_similar_title_duplicates()
            duplicates.extend(similar_title_duplicates)
            analysis_text.append(
                f"Similar title duplicates: {len(similar_title_duplicates)} groups"
            )

        # Create wizard lines for each duplicate group
        self.duplicate_line_ids.unlink()
        line_vals = []

        for i, duplicate_group in enumerate(duplicates):
            for movie in duplicate_group:
                line_vals.append(
                    {
                        "wizard_id": self.id,
                        "movie_id": movie.id,
                        "group_number": i + 1,
                        "is_recommended_keep": self._is_recommended_keep(
                            movie, duplicate_group
                        ),
                        "duplicate_reason": self._get_duplicate_reason(duplicate_group),
                    }
                )

        self.env["tmdb.data.cleanup.wizard.line"].create(line_vals)

        # Update results
        self.write(
            {
                "duplicate_count": len(duplicates),
                "analysis_results": "\n".join(analysis_text)
                + f"\n\nTotal duplicate groups: {len(duplicates)}",
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": "Cleanup Analysis Results",
            "res_model": "tmdb.data.cleanup.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_analyze_duplicates(self):
        """Analyze duplicates without making changes - just refresh the view"""
        self.ensure_one()

        if not self.duplicate_line_ids:
            raise UserError("Please run duplicate detection first.")

        return {
            "type": "ir.actions.act_window",
            "name": "Duplicate Analysis Results",
            "res_model": "tmdb.data.cleanup.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_process_duplicates(self):
        """Process duplicates based on selected action"""
        self.ensure_one()

        if not self.duplicate_line_ids:
            raise UserError("Please run duplicate detection first.")

        if self.action_type == "merge":
            return self._merge_duplicates()
        elif self.action_type == "delete":
            return self._delete_duplicates()

    def action_create_test_duplicates(self):
        """Create dummy duplicate movies for testing the cleanup wizard"""
        self.ensure_one()

        movie_model = self.env["tmdb.movie"]

        # Sample movies data for creating duplicates
        test_movies = [
            {
                "title": "The Matrix",
                "original_title": "The Matrix",
                "overview": "A computer programmer discovers reality is a simulation.",
                "release_date": "1999-03-30",
                "vote_average": 8.7,
                "vote_count": 15000,
                "popularity": 450.0,
                "director": "The Wachowskis",
            },
            {
                "title": "Inception",
                "original_title": "Inception",
                "overview": "A thief enters dreams to steal secrets.",
                "release_date": "2010-07-16",
                "vote_average": 8.8,
                "vote_count": 18000,
                "popularity": 500.0,
                "director": "Christopher Nolan",
            },
            {
                "title": "Avatar",
                "original_title": "Avatar",
                "overview": "A marine fights aliens on a distant planet.",
                "release_date": "2009-12-18",
                "vote_average": 7.8,
                "vote_count": 20000,
                "popularity": 600.0,
                "director": "James Cameron",
            },
        ]

        created_count = 0

        # Find next available TMDB ID range to avoid conflicts
        existing_ids = movie_model.search([]).mapped("tmdb_id")
        existing_ids = [id for id in existing_ids if id is not False]

        # Start from a high number to avoid conflicts with real TMDB data
        start_id = 999000
        while any(id >= start_id and id < start_id + 100 for id in existing_ids):
            start_id += 100

        for i, movie_data in enumerate(test_movies):
            # Create original movie with safe TMDB ID
            base_tmdb_id = start_id + (i * 10)
            original_movie = movie_model.create(
                {
                    **movie_data,
                    "tmdb_id": base_tmdb_id,
                }
            )

            # Create duplicate with same title and date (but different TMDB ID)
            duplicate_1 = movie_model.create(
                {
                    **movie_data,
                    "title": movie_data["title"],  # Same title
                    "tmdb_id": base_tmdb_id + 1,  # Different TMDB ID
                    "overview": f"Duplicate 1: {movie_data['overview']}",
                    "vote_average": (movie_data["vote_average"] or 0) - 0.5,
                }
            )

            # Create another duplicate with same title and date
            duplicate_2 = movie_model.create(
                {
                    **movie_data,
                    "title": movie_data["title"],  # Same title
                    "tmdb_id": base_tmdb_id + 2,  # Different TMDB ID
                    "overview": f"Duplicate 2: {movie_data['overview']}",
                    "vote_average": (movie_data["vote_average"] or 0) + 0.3,
                }
            )

            # Create similar title duplicate (same year)
            duplicate_3 = movie_model.create(
                {
                    **movie_data,
                    "title": f"{movie_data['title']}: Extended Edition",  # Similar title
                    "tmdb_id": base_tmdb_id + 3,
                    "overview": f"Extended version: {movie_data['overview']}",
                    "vote_average": (movie_data["vote_average"] or 0) + 0.2,
                }
            )

            created_count += 4  # Original + 3 duplicates

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Test Data Created",
                "message": f"Created {created_count} test movies with duplicates for testing.",
                "type": "success",
            },
        }

    def _find_tmdb_id_duplicates(self):
        """Find movies with duplicate TMDB IDs"""
        duplicates = []
        movie_model = self.env["tmdb.movie"]

        # Get all movies grouped by tmdb_id where count > 1
        self.env.cr.execute("""
            SELECT tmdb_id, COUNT(*) as count
            FROM tmdb_movie
            WHERE tmdb_id IS NOT NULL
            GROUP BY tmdb_id
            HAVING COUNT(*) > 1
        """)

        duplicate_tmdb_ids = [row[0] for row in self.env.cr.fetchall()]

        for tmdb_id in duplicate_tmdb_ids:
            duplicate_movies = movie_model.search([("tmdb_id", "=", tmdb_id)])
            if len(duplicate_movies) > 1:
                duplicates.append(duplicate_movies)

        return duplicates

    def _find_title_date_duplicates(self):
        """Find movies with same title and release date"""
        duplicates = []
        movie_model = self.env["tmdb.movie"]

        # Get all movies grouped by title and release_date where count > 1
        self.env.cr.execute("""
            SELECT title, release_date, COUNT(*) as count
            FROM tmdb_movie
            WHERE title IS NOT NULL AND title != ''
            GROUP BY title, release_date
            HAVING COUNT(*) > 1
        """)

        duplicate_pairs = [(row[0], row[1]) for row in self.env.cr.fetchall()]

        for title, release_date in duplicate_pairs:
            domain = [("title", "=", title)]
            if release_date:
                domain.append(("release_date", "=", release_date))
            else:
                domain.append(("release_date", "=", False))

            duplicate_movies = movie_model.search(domain)
            if len(duplicate_movies) > 1:
                duplicates.append(duplicate_movies)

        return duplicates

    def _find_similar_title_duplicates(self):
        """Find movies with similar titles in the same year"""
        duplicates = []
        movie_model = self.env["tmdb.movie"]

        # Get all movies with release dates
        movies_with_dates = movie_model.search([("release_date", "!=", False)])

        # Group by year
        year_groups = {}
        for movie in movies_with_dates:
            year = movie.release_date.year
            if year not in year_groups:
                year_groups[year] = []
            year_groups[year].append(movie)

        # Check for similar titles within each year
        for year, movies in year_groups.items():
            if len(movies) < 2:
                continue

            # Simple similarity check - normalize titles and compare
            title_groups = {}
            for movie in movies:
                normalized_title = self._normalize_title(movie.title)
                if normalized_title not in title_groups:
                    title_groups[normalized_title] = []
                title_groups[normalized_title].append(movie)

            # Add groups with more than one movie
            for title, title_movies in title_groups.items():
                if len(title_movies) > 1:
                    duplicates.append(movie_model.browse([m.id for m in title_movies]))

        return duplicates

    def _normalize_title(self, title):
        """Normalize title for comparison"""
        if not title:
            return ""

        # Convert to lowercase, remove common articles and punctuation
        normalized = title.lower()
        normalized = normalized.replace("the ", "").replace(" the", "")
        normalized = normalized.replace("a ", "").replace(" a", "")
        normalized = normalized.replace("an ", "").replace(" an", "")

        # Remove common punctuation
        for char in ".,!?;:":
            normalized = normalized.replace(char, "")

        # Remove extra spaces
        normalized = " ".join(normalized.split())

        return normalized

    def _is_recommended_keep(self, movie, duplicate_group):
        """Determine if this movie should be recommended to keep"""
        if self.keep_preference == "newest":
            return movie == max(duplicate_group, key=lambda m: m.create_date)
        elif self.keep_preference == "most_complete":
            return movie == self._get_most_complete_record(duplicate_group)
        elif self.keep_preference == "highest_rating":
            return movie == max(duplicate_group, key=lambda m: m.vote_average or 0)
        else:  # manual
            return False

    def _get_most_complete_record(self, movies):
        """Get the most complete record from a group"""

        def completeness_score(movie):
            score = 0
            if movie.overview:
                score += 1
            if movie.director:
                score += 1
            if movie.poster_path:
                score += 1
            if movie.backdrop_path:
                score += 1
            if movie.genre_ids:
                score += len(movie.genre_ids)
            if movie.vote_count:
                score += 1
            return score

        return max(movies, key=completeness_score)

    def _get_duplicate_reason(self, duplicate_group):
        """Get the reason why these movies are considered duplicates"""
        if len(duplicate_group) < 2:
            return "No duplicates"

        first_movie = duplicate_group[0]
        second_movie = duplicate_group[1]

        if first_movie.tmdb_id == second_movie.tmdb_id:
            return "Same TMDB ID"
        elif (
            first_movie.title == second_movie.title
            and first_movie.release_date == second_movie.release_date
        ):
            return "Same Title and Release Date"
        else:
            return "Similar Title"

    def _merge_duplicates(self):
        """Merge duplicate records"""
        processed = 0

        # Group lines by group_number
        groups = {}
        for line in self.duplicate_line_ids:
            if line.group_number not in groups:
                groups[line.group_number] = []
            groups[line.group_number].append(line)

        for group_num, lines in groups.items():
            if len(lines) < 2:
                continue

            # Find the record to keep
            keep_line = None
            if self.keep_preference == "manual":
                recommended_lines = [line for line in lines if line.is_recommended_keep]
                if not recommended_lines:
                    continue  # Skip if no manual selection
                keep_line = recommended_lines[0]
            else:
                recommended_lines = [line for line in lines if line.is_recommended_keep]
                if not recommended_lines:
                    # If no line is marked as recommended, keep the first one
                    keep_line = lines[0]
                else:
                    keep_line = recommended_lines[0]

            # Merge other records into the kept record
            movies_to_remove = [
                line.movie_id for line in lines if line.id != keep_line.id
            ]

            try:
                self._merge_movie_data(keep_line.movie_id, movies_to_remove)

                # Delete the duplicate records
                for movie in movies_to_remove:
                    movie.unlink()

                processed += 1

            except Exception as e:
                _logger.error(f"Error merging duplicate group {group_num}: {e}")
                continue

        self.processed_count = processed

        # Clear duplicate data after successful processing
        self.duplicate_line_ids.unlink()
        self.duplicate_count = 0
        self.analysis_results = f"Processing completed successfully!\n\nMerged {processed} duplicate groups.\n\nRun 'Detect Duplicates' again to check for remaining duplicates."

        # Show toast notification
        message = f"Successfully merged {processed} duplicate groups."
        self.env["bus.bus"]._sendone(
            self.env.user.partner_id,
            "simple_notification",
            {
                "type": "success",
                "title": "Merge Complete",
                "message": message,
            },
        )

        return {
            "type": "ir.actions.act_window",
            "name": "Data Cleanup Complete",
            "res_model": "tmdb.data.cleanup.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _delete_duplicates(self):
        """Delete duplicate records based on preference"""
        processed = 0

        # Group lines by group_number
        groups = {}
        for line in self.duplicate_line_ids:
            if line.group_number not in groups:
                groups[line.group_number] = []
            groups[line.group_number].append(line)

        for group_num, lines in groups.items():
            if len(lines) < 2:
                continue

            # Delete all but the recommended record
            movies_to_delete = [
                line.movie_id for line in lines if not line.is_recommended_keep
            ]

            for movie in movies_to_delete:
                movie.unlink()

            processed += len(movies_to_delete)

        self.processed_count = processed

        # Clear duplicate data after successful processing
        self.duplicate_line_ids.unlink()
        self.duplicate_count = 0
        self.analysis_results = f"Processing completed successfully!\n\nDeleted {processed} duplicate records.\n\nRun 'Detect Duplicates' again to check for remaining duplicates."

        # Show toast notification
        message = f"Successfully deleted {processed} duplicate records."
        self.env["bus.bus"]._sendone(
            self.env.user.partner_id,
            "simple_notification",
            {
                "type": "success",
                "title": "Deletion Complete",
                "message": message,
            },
        )

        return {
            "type": "ir.actions.act_window",
            "name": "Data Cleanup Complete",
            "res_model": "tmdb.data.cleanup.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _merge_movie_data(self, target_movie, source_movies):
        """Merge data from source movies into target movie"""
        if not source_movies:
            return

        update_vals = {}
        current_genre_ids = set(target_movie.genre_ids.ids)

        # Merge fields by taking the most complete data
        for source_movie in source_movies:
            if not target_movie.overview and source_movie.overview:
                update_vals["overview"] = source_movie.overview

            if not target_movie.director and source_movie.director:
                update_vals["director"] = source_movie.director
                update_vals["director_id"] = (
                    source_movie.director_id.id if source_movie.director_id else False
                )

            if not target_movie.poster_path and source_movie.poster_path:
                update_vals["poster_path"] = source_movie.poster_path

            if not target_movie.backdrop_path and source_movie.backdrop_path:
                update_vals["backdrop_path"] = source_movie.backdrop_path

            # Merge genres progressively
            if source_movie.genre_ids:
                new_genre_ids = set(source_movie.genre_ids.ids)
                current_genre_ids = current_genre_ids.union(new_genre_ids)

            # Keep higher vote counts and ratings
            if source_movie.vote_count and source_movie.vote_count > (
                target_movie.vote_count or 0
            ):
                update_vals["vote_count"] = source_movie.vote_count
                update_vals["vote_average"] = source_movie.vote_average

        # Update genres if there are new ones
        if current_genre_ids != set(target_movie.genre_ids.ids):
            update_vals["genre_ids"] = [(6, 0, list(current_genre_ids))]

        # Apply updates if any
        if update_vals:
            target_movie.write(update_vals)


class TMDBDataCleanupWizardLine(models.TransientModel):
    _name = "tmdb.data.cleanup.wizard.line"
    _description = "TMDB Data Cleanup Wizard Line"

    wizard_id = fields.Many2one(
        "tmdb.data.cleanup.wizard", string="Wizard", required=True
    )
    movie_id = fields.Many2one("tmdb.movie", string="Movie", required=True)
    group_number = fields.Integer(string="Group", help="Duplicate group number")
    is_recommended_keep = fields.Boolean(
        string="Keep This Record", help="Recommended record to keep"
    )
    duplicate_reason = fields.Char(
        string="Duplicate Reason", help="Why this is considered a duplicate"
    )

    # Related fields for display
    movie_title = fields.Char(related="movie_id.title", string="Title")
    movie_tmdb_id = fields.Integer(related="movie_id.tmdb_id", string="TMDB ID")
    movie_release_date = fields.Date(
        related="movie_id.release_date", string="Release Date"
    )
    movie_vote_average = fields.Float(related="movie_id.vote_average", string="Rating")
    movie_overview = fields.Text(related="movie_id.overview", string="Overview")
