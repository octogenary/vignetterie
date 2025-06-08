import os
import subprocess
from datetime import datetime
import threading
from python_json_config import ConfigBuilder, Config
from textwrap import dedent
import shutil
import sys


class Vignette(object):
    def __init__(self, parent: "Vignetterie", name: str, config: Config):
        print(f"Starting {name}.")
        self.name = name
        self.raw_date = (
            subprocess.run(
                [
                    "git",
                    "log",
                    "-1",
                    """--pretty="%ct""" "",
                    f"{config.vignettes_root}{name}.tex",
                ],
                stdout=subprocess.PIPE,
            )
            .stdout.decode("utf-8")[1:]
            .strip()
        )
        self.date = (
            datetime.utcfromtimestamp(int(self.raw_date)).strftime(
                "%H.%M temps universel coordonné, %-d %B %Y"
            )
            if self.raw_date
            else "date inconnue"
        )
        os.makedirs(config.build, exist_ok=True)
        with open(f"{config.vignettes_root}{name}.tex") as source_file, open(
            f"{config.build}{name}.tex", "w"
        ) as standalone_tex_file:
            original_tex = source_file.read()
            metadata, body = original_tex.split("===")
            metadata_lines = metadata.split("\n")
            self.title, self.tags = metadata_lines[0], metadata_lines[2].split(", ")
            standalone_tex = dedent(
                r"""
                \documentclass{article}
                \usepackage{../tex/resources/vignetterie}
                \bibliography{../tex/resources/vignetterie.bib}
                \begin{document}
                """
                + body
                + r"""
                \printbibliography[heading=none]
                \end{document}"""
            )
            standalone_tex_file.write(standalone_tex)
        try:
            if (
                "-r" in sys.argv
                or not self.raw_date
                or self.raw_date
                and int(self.raw_date)
                > os.path.getmtime(
                    f"{config.output_root}{config.vignette_output}{name}.html"
                )
            ):
                subprocess.Popen(
                    f"make4ht -ul --build-file {config.build_file} "
                    f"--output-dir {config.standalone_output} "
                    f"--config {config.make4ht_config} "
                    f"--build-dir {config.build} "
                    f"{config.build}{name}.tex ",
                    shell=True,
                ).wait()
        except OSError:
            pass
        os.makedirs(config.standalone_output, exist_ok=True)
        os.makedirs(f"{config.output_root}{config.vignette_output}", exist_ok=True)
        with open(f"{config.standalone_output}{name}.html") as original_html_file, open(
            f"{config.standalone_output}{name}.css"
        ) as original_css_file, open(
            f"{config.output_root}{config.vignette_output}{name}.html", "w"
        ) as html_output, open(
            f"{config.output_root}{config.vignette_output}{name}.css", "w"
        ) as css_output:
            html_body = original_html_file.read().split("<body>")[1].split("</body")[0]
            tags = ", ".join(
                [
                    f"<a href='../etiquettes/{tag.replace(' ', '-').lower()}.html'>{tag}</a>"
                    for tag in self.tags
                ]
            )
            html = dedent(
                f"""
                <!DOCTYPE html>
                <html>
                <head><title>{self.title}</title>
                <meta charset="utf-8" />
                <meta content='width=device-width,initial-scale=1' name='viewport' /> 
                <link href='{name}.css' rel='stylesheet' type='text/css' /> 
                </head>
                <body>
                <header>
                    <h2><a href="../index.html">La Vignetterie.</a></h2>
                </header>
                <main>
                <h1>{self.title}</h1>
                {html_body}
                <h2>À propos.</h2>
                <p>Étiquettes : {tags}.</p>
                <p>Dernière mise à jour : {self.date}.</p>
                </main>
                </body>
                </html>"""
            )
            html_output.write(html)
            css_output.write(original_css_file.read())
        for tag in self.tags:
            parent.tag_vignette(self, tag)

    def __str__(self):
        return f"Vignette(Name: {self.name})"


class Vignetterie(object):
    def __init__(self, config: Config):
        subprocess.Popen("rm -rf ../output/*", shell=True)
        self.tags = {}
        self.config = config
        threads = [
            threading.Thread(target=Vignette, args=(self, path[:-4], config))
            for path in os.listdir(config.vignettes_root)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        print("make4ht phase finished.")
        os.makedirs(f"{config.output_root}{config.tag_output}", exist_ok=True)
        for tag in self.tags:
            self.generate_tag_page(tag)
        self.generate_index()
        for file, dest in self.config.to_copy:
            shutil.copyfile(file, dest)

    def tag_vignette(self, vignette: Vignette, tag: str):
        if tag in self.tags:
            self.tags[tag].append(vignette)
        else:
            self.tags[tag] = [vignette]

    def generate_tag_page(self, tag: str):
        vignettes = self.tags[tag]
        html_body = " · ".join(
            [
                f"<a href='../vignettes/{vignette.name}.html'>{vignette.title} ({vignette.date})</a>"
                for vignette in vignettes
            ]
        )
        html = dedent(
            f"""
                <!DOCTYPE html>
                <html>
                <head><title>{tag}</title>
                <meta charset="utf-8" />
                <meta content='width=device-width,initial-scale=1' name='viewport' /> 
                <link href='../main.css' rel='stylesheet' type='text/css' /> 
                </head>
                <body>
                <header>
                    <h2><a href="../index.html">La Vignetterie.</a></h2>
                </header>
                <main>
                <h1>ce qui concerne : {tag}</h1>
                {html_body}
                </main>
                </body>
                </html>"""
        )
        with open(
            f"{config.output_root}{config.tag_output}{tag.replace(' ', '-').lower()}.html",
            "w",
        ) as f:
            f.write(html)

    def generate_index(self):
        with open(config.apropos) as f, open(
            f"{config.output_root}index.html", "w"
        ) as output:
            apropos = f.read()
            tags = " · ".join(
                [
                    f"<a href='etiquettes/{tag.replace(' ', '-').lower()}.html'>{tag} ({len(self.tags[tag])})</a>"
                    for tag in sorted(self.tags, key=lambda t: (-len(self.tags[t]), t.lower()))
                ]
            )
            html = dedent(
                f"""
                    <!DOCTYPE html>
                    <html>
                    <head><title>La Vignetterie.</title>
                    <meta charset="utf-8" />
                    <meta content='width=device-width,initial-scale=1' name='viewport' /> 
                    <link href='main.css' rel='stylesheet' type='text/css' /> 
                    </head>
                    <body>
                    <header>
                        <h1>La Vignetterie.</h1>
                    </header>
                    <main>
                    <h2>À propos.</h2>
                    {apropos}
                    <h2>Étiquettes.</h2>
                    {tags}
                    </main>
                    </body>
                    </html>"""
            )
            output.write(html)

    def __str__(self):
        return "Vignetterie"


if __name__ == "__main__":
    builder = ConfigBuilder()
    config = builder.parse_config("config.json")
    for field in [
        "vignettes_root",
        "resources_root",
        "output_root",
        "build",
        "vignette_output",
        "tag_output",
        "build_file",
        "make4ht_config",
        "to_copy",
    ]:
        builder.validate_field_type(field, str)
    Vignetterie(config)
