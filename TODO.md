# TODO

## GitHub Actions

- [ ] **Prebuild Docker images with GitHub Actions**
  - Create GitHub Actions workflow to build and push Docker images to GitHub Container Registry (ghcr.io)
  - Build `shairport-sync` image with ALAC decoder and AirPlay 2 support (`--with-apple-alac` and `--with-airplay-2` flags)
  - Build `airglow-web` image
  - Build `avahi` image
  - Build `nqptp` image
  - Tag images with version tags and `latest`
  - Update install script to use pre-built images from ghcr.io instead of building from source
  - This will significantly speed up installations and ensure consistent builds across environments

