# Dataset Construction Explained

#### Table of Contents

1. [Frame Extraction and Similar Image Removal](#stage-1-frame-extraction-and-similar-image-removal)
1. [Character Detection and Cropping](#stage-2-character-detection-and-cropping)
1. [Character Clustering / Classification](#stage-3-character-clustering-or-classification)
1. [Image Selection and Resizing](#stage-4-image-selection-and-resizing)
1. [Tagging and Captioning](#stage-5-tagging-and-captioning)
1. [Folder Arrangement](#stage-6-folder-arrangement)
1. [Dataset Balancing](#stage-7-dataset-balancing)

I will also provide below approximate running time on my own laptop with a RTX 3070 Ti. The command line arguments listed here are not exhaustive. Please use `--help` to get the entire list.

:bulb: In total it takes me a little more than 2 hours to process four episodes (24 mins each).


## Stage 1: Frame Extraction and Similar Image Removal

**Extract 5000~10000 frames per episode of 24 minutes and remove similar images**

- This stage take 5~10 minutes per episode on my laptop.
- `--src_dir` should be a folder containing the videos to process.
- Output folder: `/path/to/dataset_dir/intermediate/{image_type}/raw`
- After this stage, you can go over the images to select those you want to keep.

### Frame extraction

**Requirements: `ffmpeg` with [mpdecimate](http://underpop.online.fr/f/ffmpeg/help/mpdecimate.htm.gz) filter and cuda support**

For the moment being, I directly rely on calling `ffmpeg` command like

```
file_pattern="${dst_ep_dir}/${prefix}EP$((ep_init+i))_%d.png"

ffmpeg -hwaccel cuda -i $filename -filter:v \
"mpdecimate=hi=64*200:lo=64*50:frac=0.33,setpts=N/FRAME_RATE/TB" \
-qscale:v 1 -qmin 1 -c:a copy "$file_pattern"
```

**:warning: It is important to ensure that every image has different name at this stage. Otherwise some images will be overwritten later.**

- `image_prefix`: This allows you to give a prefix to the extracted images.
- `ep_init`: When you split the process in multiple runs. You should either set different `--image_prefix` or adjust `--ep_init` to specify which episode you start from. Note that the processing order is obtained by sorting the filenames, and thus the episode given here could be different from the actual one if the filename does not have a consistent format.


The use of [mpdecimate](http://underpop.online.fr/f/ffmpeg/help/mpdecimate.htm.gz) filter removes consecutive frames that are too similar. Enabling the filter makes a big difference in both processing speed and the number of extracted frames (probably 10 times fewer images with the filter). For now I have not found a python-only way to achieve the same.  
An even more aggressive approach would be to keep only the key frames (I may add the option later).

### Similar Image Removal

This step uses `fiftyone` and mobilenet to remove similar images, reduces dataset size by a factor of 2 to 10 depending on the anime.

Since the extracted images can take a lot of place, I have made the decision to combine the two steps and perform removal for each episode independently after its frames are extracted. I also do a final pass on all the extracted images at the end to remove repeated images in notably OP and ED.

- `no_remove_similar`: Put this argument to skip this step.
- `similar_thresh`: The threshold above which we judge that two images are too similar. Default is 0.985.
- `detect_duplicate_model`: You can use other model than the default mobilenet. Check `fiftyone` documentation to see what models are available.

:warning: If you are also using Ubuntu 22.04 you may encounter problem importing `fiftyone` once it gets installed. Please check [this thread](https://github.com/voxel51/fiftyone/issues/1803) for some troubleshooting.


## Stage 2: Character Detection and Cropping

**Crop independent characters into a separate folder**

- This stage take 5~10 minutes per episode on my laptop.
- If you start from this stage, please set `--src_dir` to the folder containing all the images to process (like the `.../raw` folder from the first stage).
- Output folder:  `/path/to/dataset_dir/intermediate/{image_type}/cropped`
- After this stage, you can go over the images to select those you want to keep.

### Command line arguments

- `min_crop_size`: Minimum size for cropped image (shorter edge). Smaller images are dropped. Default is 320.


## Stage 3: Character Clustering or Classification

**0-shot character clustering or few-shot character classification without training**

- This takes ~5 mins for 3k images on my laptop (from 4 episodes).
- If you start from this stage, please set `--src_dir` to the folder containing images to classify (like the `.../cropped` folder from the second stage or the `.../classified` folder from this stage).
- Output folder:  `/path/to/dataset_dir/intermediate/{image_type}/classified`
- **Recommended:** After this stage, you can go over the images to rename clusters, construct`--character_ref_dir` and rerun from this stage, and move character images around for correction. More details follow.

### Detailed instructions

The working horse of this new pipeline is the [ccip embedding](https://deepghs.github.io/imgutils/main/api_doc/metrics/ccip.html). It allows to perform 0-shot character clustering!

Nonetheless, even if the model knows how to cluster characters it does not know the names of characters. Moreover, a character can be split into multiple clusters in an undesired way and some character may just contain random people from the anime. There are two ways to fix this.
- Provide `--character_ref_dir` as explained in README to perform few-shot classification.
- Go through the sub-folders of `.../classified`, merge, and rename them accordingly. All the non-relevant characters should go into `-1_noise` folder.

A recommendation is to first run without any reference folder. Use the obtained sub-folders to construct reference folder and run this stage again. Finally, you can go through all the resulting sub-folders your self to check the content and move characters to the correct folder or remove images with no characters.

### Remarks

- ccip embeddings are cached, so you will not compute them again if you start from `.../classified`.
- You only need to move the images during manual inspection. In the next stage the program will find the corresponding metadata and cached file themselves. (For the moment you will not be able resume from this stage without corresponding metadata in the same folder though.)
- The character name would be a random string if you run without `--character_ref_folder`. This will be ok for pivotal tuning methods where we associate text embeddings to characters as we can rename embeddings afterwards.
- :warning: Avoid putting comma in character names if you use `--load_aux characters` later as character names are separated by commas and a character name with commas will then be recognized as multiple characters

### Technical details

TODO


## Stage 4: Image Selection and Resizing

**Resize images with characters to training folder with resizing**

- This takes ~1 min per 1k images on my laptop.
- If you start from this stage, please set `--src_dir` to the folder containing both `classified` and `raw` (`/path/to/dataset_dir/intermediate/{image_type}` by default).
- Output folder:  `/path/to/dataset_dir/tranining/{image_type}`
- After this stage, you can go over the images to select those you want to keep.

The images obtained after this stage are meant to be the ones used for training.

### Image selection criteria

The folder names from `.../classified` directory are first read and save in the `characters` field of the images' metadata (cropped and original alike). Folder names should be of the form `XXX_{character_name}`. After this, the images are selected in the following way

- For cropped images: select those with size smaller than half of the original image
- For original images:
    - Selected those with characters
    - Selected `--n_anime_reg` images with no characters for style regularization (use all if there are not enough no character images)

### Command line arguments

- `no_resize`: Copy file instead of resize.
- `filter_again`: Go through the dataset and remove similar images again as in the first stage (cropped images can be similar even the full image is not).
- `max_size`: Max image size to resize to (the shorter edge is aligned). Default is 768.
- `image_save_ext`: Image extension for resized image. Default is `.webp`.
- `n_anime_reg`: Number of images with no characters to put in the dataset (can be background, random people, etc.).


## Stage 5: Tagging and Captioning

**Tag, prune tags, and caption**

- This takes 1~2 mins per 1k images on my laptop.
- If you start from this stage, please set `--src_dir` to the training folder with images to tag and caption (can be independently used as tagger).
- In-place operation.
- After this stage, you can edit tags and characters yourself using suitable tools, especially if you put `--save_aux processed_tags characters`. More details follow.

### Tagging

In this phase, we use a publicly available taggers to tag images.

- `tagging_method`: Choose a tagger available in [waifuc](https://github.com/deepghs/waifuc).  
    Choices: deepdanbooru, wd14_vit, wd14_convnext, wd14_convnextv2, wd14_swinv2, mldanbooru.  
    Default is wd14_convnextv2.
- `overwrite_tags`: Overwrite existing tags even if tags exist in metadata.
- `tag_threshold`: Threshold for tagger.


### Tag pruning

For now tag pruning goes through 3 steps. You can deactivate tag pruning by setting `--pruned_mode none`.

- Pruned blacklisted tags. Remove tags in the file `--blacklist_tags_file` (one tag per line). Use [blacklist_tags.txt](../tag_filtering/blacklist_tags.txt) by default.
- Pruned overlap tags. This includes tags that are sub-string of other tags, and overlapped tags specified in `--overlap_tags_file`. Use [overlap_tags.json](../tag_filtering/overlap_tags.json) by default.
- By default `pruned_mode` is set to `character`. In this case, if an image contains character, we try to remove hair, eye, and skin related tags using hard defined rules. Set `--pruned_mode minimal` to skip this step.

All the tags are saved to the field `processed_tags` of metadata. We also process by this field if it exists by default (unless `--overwrite_tags` is used). If you want to process from the field `tags`, you should use `--process_from_original_tags`. 

### Tag ordering

I consistently put 'solo', '1girl', '1boy', 'Xgilrs', 'Xboys' at the beginning. After that, `sort_mode` can be one of the following
- `original`: use original order
- `shuffle`: random shuffling
- `score`: only applicable when tagger is used. Tagger produces score. We then put tags with higher score in front.

After sorting at most `--max_tag_number` tags are kept.

### Captioning

This step uses tags and other fields to produce captions, saved in `caption` field of metadata.

- `separator`: Tags are always separated by commas. This is used to separate characters and information from different fields.
- `use_XXX_prob`: The probability of using some sort of information. Use `--help` to see all. Some of them have no effect for the moment.
- `caption_no_underscore`: Remove all underscores from captions (note that underscores are always removed from tags---except for '\^\_\^').

### Manual inspection: Tag and character editing

You can use `--save_aux` to save some metadata fields to separate files and use `--load aux` to load them.

Typically, you can run with `--save_aux processed_tags characters`. You then get files with names like `XXX.processed_tags` and `XXX.characters`. These can be batch edited with tools such as [dataset-tag-editor](https://github.com/toshiaki1729/stable-diffusion-webui-dataset-tag-editor) or [BatchPrompter](https://github.com/Snowad14/BatchPrompter). These changes can then be loaded with `--load_aux processed_tags characters`. Remember to run again from this stage to update captions.

- Since tags are not overwritten by default, you don't need to worry about tagger overwriting the edited tags.
- It is better to correct detected characters after stage 3. Here you can edit `XXX.characters` to add non-detected characters (like viewed from behind).
- :warning: If you edit caption directly, running this stage again will overwrite the changes.

## Stage 6: Folder Arrangement

**Arrange folder in n_characters/character format**

- This takes 30 secs to 1 min per 1K images on my laptop.
- If you start from this stage, please set `--src_dir` to the training folder to arrange (`/path/to/dataset_dir/training/{image_type}` by default).
- In-place operation.

Effect of `--max_character_number` and `--min_images_per_combination` are readily mentioned in readme. You can also set `--arrange_format character` to remove the level that specifies the number of characters.


## Stage 7: Dataset Balancing

**Balanced dataset by computing repeat/multiply for each sub-folder**

- This runs instantaneously for 5K images.
- If you start from this stage, please set `--src_dir` to the training folder containing all training images, screenshots, fanarts, regularization images, or whatever (`/path/to/dataset_dir/training` by default).
- In-place operation.

I assume that we have multiple types of images. They should be all put in the training folder for this stage to be effective.

### Technical details

We generate her the `multipy.txt` in each image folder to indicate the number of times that the images of this folder should be used in a repeat, with the goal to balance between different concepts during training.

To compute the multiply of each image folder, we first compute its sampling probability. We do this by going through the hierarchy, and at each node, we sample each child with probability proportional to its weight. Its weight is default to 1 but can be changed with the csv file provided through `--weight_csv` ([default_weighting.csv](../csv_examples/default_weighting.csv) is used by dedfault). It first searches for the folder name of the child directory and next searches for the pattern of the entire path (path of `src_dir` plus path from `src_dir` to the directory) as understood by `fnmatch`.

For example, consider the folder structure
```
├── ./1_character
│   ├── ./1_character/class1
│   └── ./1_character/class2
└── ./others
    ├── ./others/class1
    └── ./others/class3
```
and the csv
```
1_character, 3
class1, 4
*class2, 6
```
For simplicity (and this should be the good practice), assume images are only in the class folders. Then, the sampling probabilities of `./1_character/class1`, `./1_character/class2`, `./others/class1`, and `./others/class3` are respectively 0.75 * 0.4 = 0.3, 0.75 * 0.6 = 0.45, 0.25 * 0.8 = 0.2, and 0.25 * 0.2 = 0.05. Note that the same weight of `class1` can yield different sampling probability because of the other folders at the same level can have different weights (in this case `./1_character/class2` has weight 6 while `./others/class3` has weight 1).

Now that we have the sampling probability of each image folder, we can compute the weight per image by diving it by the number of images in that image folder. Finally, we convert it into multiply by setting the minimum multiply to `--min_multiply` (default to 1). The argument `--max_multiply` sets a hard limit on the maximum multiply of each image folder above which we clip to this value. After running the command you can check the log file to see if you are satisfied with the generated multiplies/repeats.