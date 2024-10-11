# Sentinel

This repository hosts the code for the Sentinel project, a smart home security and alert system.
The repository is organised as follows:
- `model-gen`: Contains code for the machine learning pipeline used to develop the default object detection model.
- `packages`: Contains Python packages that implement the Sentinel system. Each package is managed as a Poetry project.
  - `sentinel`: Contains the code for the main executable. Currently, this contains the code for the prototype system.
  - `sentinel-core`: Contains the core interfaces (or protocols in Python speak) and data types meant to be public. Plugin authors will be interested in implementing the protocols provided by this package.
  - The `plugins/` directory contains a set of plugin packages:
    - `sentinel-desktop-notification-subscriber`: Plugin for sending desktop notifications.
    - `sentinel-mediapipe`: Plugin for using MediaPipe object detection models.
    - `sentinel-opencv`: Plugin for OpenCV video sources.
    - `sentinel-ultralytics`: Plugin for using Ultralytics object detection models.

# Running the System

As there is currently no official release, running the Sentinel system will require [Poetry](https://python-poetry.org/). After installing Poetry, run the following commands in the `packages/sentinel` directory:

```sh
$ poetry install
$ poetry run sentinel -h
```

`poetry run sentinel -h` will show a message that describes the usage of the program. Specify command line arguments as appropriate to run Sentinel.

# Running the Machine Learning Pipeline

The machine learning pipeline is implemented as a Jupyter notebook. This notebook is located at `model-gen/sentinel_model_gen/yolo.ipynb`.
To use the notebook, simply open and run it in a Jupyter environment.
Note that the notebook can be run in a Kaggle environment.

There is no need to manually retrieve the datasets used to fine-tune the model — the notebook will handle the downloading of the datasets.
