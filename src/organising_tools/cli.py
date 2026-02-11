import click
from .commands import video, dates, image, favorites

@click.group()
def cli():
    """All-in-one organising tool CLI."""
    pass

cli.add_command(video.compress)
cli.add_command(dates.fix_modified_dates)
cli.add_command(dates.fix_created_dates)
cli.add_command(dates.add_timestamp_to_filename)
cli.add_command(image.compress_image)
cli.add_command(favorites.add_folder_to_favourites)
cli.add_command(favorites.go_to_favourite_folder)
