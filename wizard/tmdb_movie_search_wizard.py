from odoo import models, fields, api
from odoo.exceptions import UserError


class TMDBMovieSearchWizard(models.TransientModel):
    _name = "tmdb.movie.search.wizard"
    _description = "TMDB Movie Search Wizard"

    search_query = fields.Char(string="Search Query")
    year_filter = fields.Integer(string="Year Filter")
    limit = fields.Integer(string="Limit")
    page = fields.Integer(string="Page")
    genre = fields.Many2one(
        "tmdb.genre",
        string="Genre",
        help="Select a genre to filter movies by",
    )
    minscore = fields.Integer(string="Min Score")
    maxscore = fields.Integer(string="Max Score")
    minpopularity = fields.Integer(string="Min Popularity")
    maxpopularity = fields.Integer(string="Max Popularity")
    minyear = fields.Integer(string="Min Year")
    maxyear = fields.Integer(string="Max Year")
