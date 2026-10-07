import click


# from https://stackoverflow.com/a/76624494
class CustomCliGroup(click.Group):
    """Custom Cli Group for Click"""

    def command(self, *args, **kwargs):
        """Adds the ability to add `aliases` to commands."""

        def decorator(f):
            aliases = kwargs.pop("aliases", None)
            if aliases and isinstance(aliases, list):
                name = kwargs.pop("name", None)
                if not name:
                    raise click.UsageError("`name` command argument is required when using aliases.")

                base_command = super(CustomCliGroup, self).command(name, *args, **kwargs)(f)

                for alias in aliases:
                    cmd = super(CustomCliGroup, self).command(alias, *args, **kwargs)(f)
                    super_help = f"\n\n{cmd.help}" if cmd.help else ""
                    cmd.help = f"Alias for '{name}'{super_help}"
                    cmd.params = base_command.params

            else:
                cmd = super(CustomCliGroup, self).command(*args, **kwargs)(f)

            return cmd

        return decorator
