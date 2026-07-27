# ComposeKit

A project to simplify Docker container management, made with love.

It ships a single `composekit` command with three subcommands:
- `composekit sort`: sorts keys in Docker Compose files
- `composekit update`: updates Docker images
- `composekit generate`: creates Docker Compose files

See the [examples/](examples/) directory for sample container definitions
and config files you can copy and adapt:
- Generation rules: [examples/generate.yaml](examples/generate.yaml)
- Update rules: [examples/update.yaml](examples/update.yaml)
- Container definitions: [examples/containers/](examples/containers/)

## Installation

Install directly from the repository with [uv](https://docs.astral.sh/uv):
```bash
uv tool install git+https://github.com/6AMStuff/ComposeKit
```
or with [pipx](https://pipx.pypa.io/):
```bash
pipx install git+https://github.com/6AMStuff/ComposeKit
```

Pin a release by appending `@<tag>`, e.g. `@v1.0.0`.

## Usage

Each subcommand reads container definitions from a folder (defaulting to
`containers/` in the current directory) and writes the generated compose
files relative to where you run it. Point it at your own files with flags:
```bash
composekit generate -c config/generate.yaml
composekit update -c config/update.yaml
composekit sort -C containers/
```

To try it against the bundled examples from the repo root:
```bash
composekit generate -c examples/generate.yaml
```

Common flags:
- `-C/--containers PATH`: folder with container definitions
- `-c/--config PATH`: config file to load (repeatable)
- `--commit`: commit the resulting changes to the git repository (off by
  default; intended for CI)

Generate also accepts `-o/--composes PATH` and `--output PATH`. See
`composekit <command> --help` for the full list.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for more details.
