# Anime Dataset Pipeline

A 99% automatized pipeline to construct training set from anime and more for text-to-image model training

The old scripts and readme have been moved into [scripts_v1](scripts_v1).

Note that the new naming of metadata follows the convention of [waifuc](https://github.com/deepghs/waifuc) and is thus different from the name given to the older version.
For conversion please use [scripts_v1/subsidiary/convert_metadata.py](scripts_v1/subsidiary/convert_metadata.py).

**Ensure that you run this script on gpu to have reasonable processing time.**

## Basic Usage

The script `automatic_pipeline.py` allows you to construct a text-to-image training set from anime with minimum effort. All you have to do is

```bash
python automatic_pipeline.py \
    --start_stage 1 \
    --end_stage 7 \
    --src_dir /path/to/video_dir \
    --dst_dir /path/to/dataset_dir \
    --character_ref_dir /path/to/ref_image_dir \
    --image_type screenshots \
    --crop_with_head \
    --image_prefix my_favorite_anime \
    --log_prefix my_favorite_anime
```

The process is split into 7 stages as detailed in [Pipeline Explained](docs/Pipeline.md) / [Wiki](https://github.com/cyber-meow/anime_screenshot_pipeline/wiki). You can decide yourself where to start and where to end, with possibility to manually inspect and modify the dataset after each stage and resume.


- `--src_dir`: The choice of this would vary depending on `start_stage` (details provided in [Pipeline Explained](docs/Pipeline.md) / [Wiki](https://github.com/cyber-meow/anime_screenshot_pipeline/wiki)). In the case where `start_stage` is set to 1, this should be a folder containing the videos to extract frames from.
- `--dst_dir`: Place to construct dataset.
- `--character_ref_dir`: Optional. A folder containing some example images for characters you want to train for. There are two ways to organize
    - With sub-folders: You can put character images in different sub-folders. Sub-folder names are then used as character names.
    - No sub-folders. In this case anything appearing before the first _ in the file name is used as character name.
- `--image_type`: this affects folder names in the constructed dataset (see [Dataset Organization](#Dataset-Organization)) and can also be used in caption (controlled with `--use_image_type_prob`).

:bulb: **Tip:** To filter out characters or random people that you are not interested in, you can use **noise** or any character name that starts with **noise**. This will not be put in the captions later on.  
:bulb: **Tip:** You can first run from stages 1 to 3 without `--character_ref_dir` to cluster characters. Then you go through the clusters to quickly construct your reference folder and run again from stages 3 to 7 with `--character_ref_dir` now given. See [Pipeline Explained](docs/Pipeline.md) / [Wiki](https://github.com/cyber-meow/anime_screenshot_pipeline/wiki) for details.

There are a lot of possible command line arguments that allow you to configure the entire process. See all of them with
```bash
python automatic_pipeline.py --help
```

I may add the possibility to read arguments from `.toml` file later.


## Dataset Organization and Training

- Once we go through the pipeline, the dataset is hierarchically organized in `/path/to/dataset_dir/training` with `multiply.txt` in each subfolder indicating the repeat of the images from this directory. More details on this are provided in [Dataset Organization](docs/Dataset_organization.md).
- Since each trainer reads data differently. Some more steps may be required before training is performed. See [Start Training](docs/Start_training.md) for what to do for [EveryDream2](https://github.com/victorchall/EveryDream2trainer), [kohya-ss/sd-scripts](https://github.com/kohya-ss/sd-scripts), and [HCP-Diffusion](https://github.com/7eu7d7/HCP-Diffusion).

## Installation

Clone this directory and install dependencies with
```bash
git clone https://github.com/cyber-meow/anime_screenshot_pipeline
git submodule update --init --recursive

cd anime_screenshot_pipeline

# Use venv, conda or whatever you like here
python -m venv venv
source venv/bin/activate  # Syntax changes according to OS

pip3 install torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt
# run also pip install fiftyone-db-ubuntu2204 for ubuntu 22.04
cd waifuc && pip install . && cd ..
# cd waifuc ; pip install . ; cd . for powershell
```

**The first stage of the process uses [ffmpeg](https://ffmpeg.org/) from command line. Please make sure you can run ffmpege from the command line (ideally with cuda support) for this stage.**

** While I personally work on Linux, others have successfully run the scripts on Windows.

## TODO / Potential improvements

Contributions are welcome

### Main

- [x] Readme and Requirements.txt
- [x] HCP-diffusion compatibility [2023.10.08]
- [ ] .toml support
- [ ] Fanart support

### Secondary

- [x] Add size to metadata to avoid opening images for size comparison [2023.10.14]
- [x] Core tag-based pruning [2023.10.15]
- [x] Improved classification workflow that takes existing character metadata into account [2023.11.10]
- [x] Embedding initialization with hard tags
- [ ] Do not crop images that are already cropped before unless otherwise specified
- [ ] Arguments to optionally remove character combinations with too few images
- [ ] Replace ffmpeg command by built-in python functions
- [ ] Compute repeat based on metadata and trainer-dependent folder organization in the same script
- [ ] Improved tag pruning (with tag tree?)

### Advanced

- [ ] Beyond character classification: outfits, objects, backgrounds, etc.
- [ ] Image quality filtering 
- [ ] Segmentation and soft mask
- [ ] Graphical interfaces with tagging/captioning tools for manual correction



## Credits

- The new workflow is largely inspired by the fully automatic procedure for single character of [narugo1992](https://github.com/narugo1992) and is largely based on the library [waifuc](https://github.com/deepghs/waifuc)
- The [tag_filtering/overlap_tags.json](tag_filtering/overlap_tags.json) file is provided by gensen2ee
- See the [old readme](scripts_v1/README.md) as well
