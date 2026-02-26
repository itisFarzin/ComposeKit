# ComposeKit

A project to simplify Docker container management, made with love.

This project includes two commands:
- generate: creates Docker Compose files
- update: updates Docker images

Key points:
- Generation rules: [config/generate.yaml](config/generate.yaml)
- Update rules: [config/update.yaml](config/update.yaml)
- Compose files are produced automatically via GitHub Actions workflows

## Running locally
- [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
- Create a virtual env:
```bash
uv venv
```
- Install the package in editable mode:
```bash
uv pip install -e .
```
- And finally, run one of the commands based on your needs:
```bash
uv run generate
```
- or
```bash
uv run update
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for more details.
