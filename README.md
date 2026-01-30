# ComposeKit

A project to simplify Docker container management, made with love.

There are two Python scripts:
- generate.py: creates Docker Compose files
- update.py: updates Docker images

Key points:
- Generation rules: [config/generate.yaml](config/generate.yaml)
- Update rules: [config/update.yaml](config/update.yaml)
- Compose files are produced automatically via GitHub Actions workflows

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for more details.
