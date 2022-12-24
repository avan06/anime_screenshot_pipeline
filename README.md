# Anime Screenshot Dataset Pipeline

In this repository I detail the workflow that I have come out to semi-automatically build a dataset from anime for [Stable Diffusion](https://github.com/CompVis/stable-diffusion) fine-tuning.
This is a collection of many resources found on internet (credit to the orignal authors), and some python code written by myself and [ChatGPT](https://chat.openai.com/chat).
I managed to get this done on my personal laptop with 3070 Ti gpu and Ubuntu 22.04 installed.

Working through the workflow, you can get dataset organized in the following way at the end.

**Level 1**
```
├── ./1_character
├── ./2_characters
├── ./3_characters
├── ./4_characters
├── ./5_characters
├── ./6+_charcters
└── ./others
```

**Level 2**
```
├── ./1_character
│   ├── ./1_character/AobaKokona
│   ├── ./1_character/AobaMai
│   ├── ./1_character/KuraueHinata
│   ├── ./1_character/KuraueHinata Hairdown
│   ├── ./1_character/KuraueKenichi
│   ├── ./1_character/KuraueMai
│   ├── ./1_character/KurosakiHonoka
│   ├── ./1_character/KurosakiTaiki
...
```

**Level 3 (the last level)**
```
├── ./1_character
│   ├── ./1_character/AobaKokona
│   │   ├── ./1_character/AobaKokona/face_height_ratio_0-25
│   │   ├── ./1_character/AobaKokona/face_height_ratio_25-50
│   │   ├── ./1_character/AobaKokona/face_height_ratio_50-75
│   │   └── ./1_character/AobaKokona/face_height_ratio_75-100
│   ├── ./1_character/AobaMai
│   │   ├── ./1_character/AobaMai/face_height_ratio_25-50
│   │   ├── ./1_character/AobaMai/face_height_ratio_50-75
│   │   └── ./1_character/AobaMai/face_height_ratio_75-100
...
```

The dataset is organized in hierarchy in order to auto-balance between different concepts without too much need of worrying about the number of images in each class.
As far as I known, the only trainer that is compatible with such organization now is [EveryDream](https://github.com/victorchall/EveryDream-trainer) (see also [EveryDream2](https://github.com/victorchall/EveryDream2trainer#readme)) with their support of using `multiply.txt`to indicate the number of times that the images of a subfolder should be used during training.
Therefore, I also provide the instruction to generate `multiply.txt` automatically at the end. As for other trainers that are available out there, you will need to modify the data loader yourself for data balance.

On top of this, I also generate a json file for each image to store their metadata. That is, for some image `XXX.png`, there is also a corresponding `XXX.json` of for example the following content
> {"count": "2", "characters": ["KuraueHinata", "AobaKokona"], "general": "anishot yamaS2EP04", "facepos": ["fvp 42 70 fhp 22 39", "fvp 15 37 fhp 62 75"], "tags": ["long_hair", "looking_at_viewer", "blush", "short_hair", "open_mouth", "multiple_girls", "skirt", "brown_hair", "shirt", "black_hair", "hair_ornament", "red_eyes", "2girls", "twintails", "purple_eyes", "braid", "pantyhose", "outdoors", "hairclip", "bag", "sunlight", "backpack", "braided_bangs"]}

Using the json file we can create the caption easily. This will be `XXX.txt` and it may contain some like

> 2people, KuraueHinata AobaKokona, anishot yamaS2EP04, fvp 42 70 fhp 22 39 fvp 15 37 fhp 62 75, backpack, outdoors, hair_ornament, pantyhose, braid, short_hair, hairclip, skirt, shirt, long_hair, open_mouth, multiple_girls, brown_hair, bag, twintails

Enough for the introduction. Now let me explain in detail how this is achieved! The design of the workflow is quite modular so you may just need some of the following steps.

### Table of Contents

1. [Frame Extraction](#Frame-Extraction)
1. [Similar Image Removal](#Similar-Image-Removal)
1. [Automatic Tagging](#Automatic-Tagging)
1. [Face Detection](#Face-Detection)
1. [Customized Classifier](#Character-Classification-with-Few-Shot-Learning)
1. [Metadata Generation](#Metadata-Generation)
1. [Folder Rearrangement](#Folder-Arrangement)
1. [Get Ready for Training](#Get-Ready-for-Training)
1. [Using Fan Arts and Regularization Data](#Using-Fan-Arts-and-Regularization-Data)


### TODO / Potential improvements

- [ ] README.md
- [ ] Requirements.txt
- [ ] Create script for removal of similar images as alternative of jupyter notebook
- [ ] Separate folder creation, arrangement, and data augmentation from basic metadata generation
- [ ] Keep source directory structure in destination directory
- [ ] Allow more flexibility in using folder structure for final metadata generation
- [ ] (Advanced) Combined with existing tagging/captioning tool for manual correction
- [ ] (Advanced) Better few-shot learning model

## Frame Extraction

**Extract 5000~10000 frames per episode of 24 minutes**

**Requirements: `ffmpeg` with [mpdecimate](http://underpop.online.fr/f/ffmpeg/help/mpdecimate.htm.gz) filter and potentially cuda support**

The first thing to do is of course to extract frames from anime. We will use the `ffmpeg` command for this.

```
ffmpeg -hwaccel cuda -i $filename -filter:v \
"mpdecimate=hi=64*200:lo=64*50:frac=0.33,setpts=N/FRAME_RATE/TB" \
-qscale:v 1 -qmin 1 -c:a copy "$prefix"_%d.png
```

The use of [mpdecimate](http://underpop.online.fr/f/ffmpeg/help/mpdecimate.htm.gz) filter removes consecutive frames that are too similar. Enabling the filter makes a big difference in both processing speed and the number of extracted frames (probably 10 times fewer images with the filter).
Therefore, it is important to keep it on.

Of course, typing the command manually for each episode is  cumbersome. Therefore, I make the process easier with the script `extract_frames.py` that runs the command for all the files of a certain pattern from the source directory and save them in separate folder in the destination directory.

```
python extract_frames.py --src_dir /path/to/scr_dir \
--dst_dir /path/to/dst_dir \
--prefix series_episode \
--pattern "my_favorite_anime_*.mp4"
```
With the above command, if `my_favorite_anime_04.mp4` exists in `/path/to/scr_dir`, the aforementioned `ffmppeg` command is run for it and the outputs are saved to `/path/to/dst_dir/EP04/` with names `series_episode_%d.png`. I recommend using the `series_episode` pattern without `_` in series and anime names so that latter on we can read this as metadata.

## Similar Image Removal

**Reduce dataset size by a factor of 10 by removing similar images**

**Requirements: install `fiftyone` with `pip install fiftyone`**

Naturally, there are a lot of similar images in consecutive frames and even with the mpdecimate filter there are still too many similar images. Fortunately, nowadays we can easily find ready-to-use tools that compute image similarity in various ways (for example with neural network representation).

For this repository I use `fiftyone` library and follow the instructions of [this blog post](https://towardsdatascience.com/find-and-remove-duplicate-images-in-your-dataset-3e3ec818b978). The code can be found in `remove_similar.ipynb`. The jupyter notebook allows you to visualize the dataset as shown below

![Screenshot from 2022-12-23 16-02-21](https://user-images.githubusercontent.com/24396911/209356724-a7dd9fea-a46a-40a5-b505-ed4f83895dc3.png)

There are three things to set:
- `dataset_dir` where the images are found (images of all the subdirectories are loaded)
- `thresh` the threshold above which we judge that two images are too similar
- `max_compare_size` the maximum size of a chuck for comparing between images. I am not using the entire dataset here because of memory issue.

Personally I find `thresh=0.985` works well for my example so I do not bother to further visualize the dataset later. I may add a script that allows removing similar images later without launching the jupyter notebook.

#### Remarks

1. If you are also using Ubuntu 22.04 you may encounter problem importing `fiftyone` once it gets installed. I have the problem solved thanks to [this solution](https://github.com/voxel51/fiftyone/issues/1803).
2. Here are some other tools for the same task but I have not tried them
    - https://github.com/ryanfwy/image-similarity
    - https://github.com/ChsHub/SSIM-PIL


## Automatic Tagging

**Tag your images with an off-the-shelf tagger**

**Requirements (suggested done in a separate environment):**
```
pip install "tensorflow<2.11"
pip install huggingface-hub
```

Now that we have a preliminary dataset. The next step is to tag the images, again by neural networks. Note this step may be done before or after the face detection step (see pros and cons of each alternative at the end of the next section).

Nowadays we are fortunate enough to have several taggers that work quite well for anime images as we can see from [toriato/stable-diffusion-webui-wd14-tagger](https://github.com/toriato/stable-diffusion-webui-wd14-tagger#mrsmilingwolfs-model-aka-waifu-diffusion-14-tagger). I simply follow [Kohya S's blog post](https://note.com/kohya_ss/n/nbf7ce8d80f29) (in Japanese) and tag all the images by [SmilingWolf/wd-v1-4-vit-tagger](https://huggingface.co/SmilingWolf/wd-v1-4-vit-tagger/tree/main).

I made the following two simple modifications to Kohya S's script `tag_images_by_wd14_tagger.py`
1. The images of all the subdirectories are tagged
2. To distinguish tags from the actual caption that will be used by the trainer, the associated file for `XXX.png` is `XXX.png.tags` and not `XXX.txt`.

Example usage
```
 python tag_images_by_wd14_tagger.py --batch_size 16 --caption_extension ".tags" /path/to/src_dir
```
Again, credit to Kohya S. for the script and credit to SmilingWolf for the model. Other existing alternative is [DeepDanbooru](https://github.com/KichangKim/DeepDanbooru/releases) which works in a similar way and BLIP caption trained on natural images. Kohya S. also provides corresponding scripts for these. However, I heard that BLIP caption is not very helpful for anime related models.


## Face Detection

**Add metadata containing face information and arrange files into subfolders accordingly if asked to do so**

**Requirements: [anime-face-detector](https://github.com/hysts/anime-face-detector)**
```
pip install openmim
mim install mmcv-full
mim install mmdet
mim install mmpose

pip install anime-face-detector
pip install -U numpy
```

People have been working on anime face detection for years, and now there is an abundance of models out there that do this job right. I am using [hysts/anime-face-detector](https://github.com/hysts/anime-face-detector) since it seems to be more recent and this is also what Kohya S uses in [his blog post](https://note.com/kohya_ss/n/nad3bce9a3622) (in Japanese).
The basic idea here is to detect faces and add their position information to a metadata file and potentially somehow describe them in captions later on. It can also be used for cropping.

### Facedata

The metadata for `XXX.png` is named `XXX.facedata.json`. Here is one example.
> {"n_faces": 3, "abs_pos": [[175, 150, 286, 265], [512, 209, 607, 307], [688, 134, 757, 249]], "rel_pos": [[0.1708984375, 0.2604166666666667, 0.279296875, 0.4600694444444444], [0.5, 0.3628472222222222, 0.5927734375, 0.5329861111111112], [0.671875, 0.2326388888888889, 0.7392578125, 0.4322916666666667]], "max_height_ratio": 0.1996527777777778, "characters": ["unknown"], "cropped": false}

The position format is ``[left, top, right, bottom]``. Since image size may vary I also compute relative positions. To generate metadata, you then run

```
python detect_faces.py --min_face_number 1 --max_face_number 10 --max_image_size 1024 \
--src_dir /path/to/src_dir --dst_dir /path/to/dst_dir
```

With `min_face_number` and `max_face_number` it only saves images whose face number is within this range to `dst_dir`. Note that for now the images are saved directly to `dst_dir` without respecting the original folder structure. The saved images are also resized to ensure that both its width and height are smaller than `max_image_size`. If you want to keep the original image size set it to arbitrarily high value.

### Subfolder construction

The script can also arrange images into subfolder as following
```
├── ./1_faces
│   ├── ./1_faces/face_height_ratio_0-25
│   ├── ./1_faces/face_height_ratio_25-50
│   ├── ./1_faces/face_height_ratio_50-75
│   └── ./1_faces/face_height_ratio_75-100
├── ./2_faces
│   ├── ./2_faces/face_height_ratio_0-25
│   ├── ./2_faces/face_height_ratio_25-50
│   ├── ./2_faces/face_height_ratio_50-75
│   └── ./2_faces/face_height_ratio_75-100
...
```

- The first level is created if `--create_count_folder` is specified. By default it creates folders `[...]_faces` using the number of detected faces. 
The behavior however changes when `--use_character_folder` or `--use_tags` are specified. With `--use_character_folder` it creates `[...]_characters` folders using the number of characters in some folder name; with `--use_tags` it creates `[...]_people` folders with tag information thanks to the presence of `[...]girl(s)` and `[...]boy(s)`. See the [fan art section](#Using-Fan-Arts-and-Regularization-Data) for details.
- The second level is created if `--create_face_ratio_folder` is specified. I am taking the height the ratio here. The range of percentage of each folder can be changed with `--face_ratio_folder_range` (default to 25).

### Other useful options

- Use `--crop` to save the largest possible square images that contain the faces (one for each detected face). The faces would be placed in the middle horizontally and near the top vertically. The corresponding `.facedata.json` are also created. If the face is too large it does a padding instead to make the resulting image square.

- Use `--move_file` if you want to move file to destination directory instead of creating new ones. `max_image_size` will be ignored for the moved images, but this does not affect the saved cropped images. For example, if your folder only contains one level of images (i.e., no subfolders) you can generate the face metadata as following
    
    ```
    python detect_faces.py --min_face_number 0 --max_face_number 100 --move_file \
    --src_dir /path/to/image_folder
    ```
    No `dst_dir` is provided here so it defaults to `src_dir`.


### Order between automatic tagging and face detection

Although these two steps are pretty much independent, there are some pros and cons of using one before another

- **Face detection -> Tagging:**
    I think this order is actually better because we can first remove images with no or too many faces. This is also the only viable direction when we do data augmentation with cropping/padding. However, the way that my code is written now makes the other way around also beneficial.
- **Tagging -> Face detection:**
    The problem is that `detect_faces.py` now does not only detect faces but also arrange folders in subfdirectories. In particular it can read tags and determine the number of people in each image and create folder accordingly. This is unfortunate.
    
In the future, I should separate folder creation and data augmentation from face detection. Then face detection and tagging can be run in any order and then we arrange folders according to the generated metadata.

## Character Classification with Few-Shot Learning

**Train your own model for series-specific concepts**

**Requirements: [anime-face-detector](https://github.com/hysts/anime-face-detector) as described above and the requirements for [arkel23/animesion](https://github.com/arkel23/animesion)**
```
cd classifier_training
pip install -r requirements.txt
cd models
pip install -e . 
```

General taggers are great, face detectors are nice, however chances are that they do not know anything specific to the anime in question. Therefore, we need to train our own model here. Luckily, foundation models are few-shot learners, so this should not be very difficult _as long as we have a good pretrained model._ Fine tuning the tagger we just used may be a solution. For now, I focus on a even simpler task for good performance, that of **character classification**.

### Basics

I use the great model of [arkel23/animesion](https://github.com/arkel23/animesion). Some weights of anime-related models can be found via this [link](https://drive.google.com/drive/folders/1Tk2e5OoI4mtVBdmjMhfoh2VC-lzW164Q) provided on their [page](https://github.com/arkel23/animesion/tree/main/classification_tagging). I particularly fine tune their best vision only model `danbooruFaces_L_16_image128_batch16_SGDlr0.001_ptTrue_seed0_warmupCosine_interTrue_mmFalse_textLenNone_maskNoneconstanttagtokenizingshufFalse_lastEpoch.ckpt`.

### Dataset Preparation

This is a simple classification task. To begin just create a directory `training_data_original` and organize the directory as following
```
├── ./class1
├── ./class2
├── ./class3
├── ./class4
...
└── ./ood
```

Put a few images in each folder that try to capture different variations of the character.
In my test 10~20 is good enough.
Then, since the classifier is meant to work with head portraits we crop the faces with `classifier_dataset_preparation/crop_and_make_dataset.py`
```
cd classifier_dataset_preparation
python crop_and_make_dataset.py --src_dir /path/to/src_dir --dst_dir /path/to/dst_dir
```

In `dst_dir` you will get the same subdirectories but containing cropped head images instead. I assume the original images only contain one face in each image.
This `dst_dir` will be our classification dataset directory. The next step is to generate `classid_classname.csv` for class id mapping and `labels.csv` for mapping between classes and image paths using `classifier_dataset_preparation/make_data_dic_imagenetsyle.py`
```
python make_data_dic_imagenetsyle /path/to/classification_data_dir
```

Finally if you want to split into training and test set you can run
```
python data_split.py /path/to/classification_data_dir/labels.csv 0.7 0.3
```
The above command does a 70%/30% train/test split.

**Remark.** I find the two scripts `make_data_dic_imagenetsyle.py` and `data_split.py` in the moeImouto dataset folder. Credit to the original author(s) of these two scripts.

### Training

First download `danbooruFaces_L_16_image128_batch16_SGDlr0.001_ptTrue_seed0_warmupCosine_interTrue_mmFalse_textLenNone_maskNoneconstanttagtokenizingshufFalse_lastEpoch.ckpt` from this [link](https://drive.google.com/drive/folders/1Tk2e5OoI4mtVBdmjMhfoh2VC-lzW164Q).
I tried to use the training script provided in [arkel23/animesion](https://github.com/arkel23/animesion) but it does not support customized dataset and transfer learning is somehow broken for [ViT with intermediate feature aggregation](https://www.gwern.net/docs/ai/anime/danbooru/2022-rios.pdf), so I modified the code a little bit and put the modified code in `classifier_training/`. Credit should go to arkel23.
```
python train.py --transfer_learning --model_name L_16 --interm_features_fc \
--batch_size=8 --no_epochs 40 --dataset_path /path/to/classification_data_dir \
--results_dir /path/to/dir_to_save_checkpoint \
--checkpoint_path /path/to/pretrained_checkpoint_dir/danbooruFaces_L_16_image128_batch16_SGDlr0.001_ptTrue_seed0_warmupCosine_interTrue_mmFalse_textLenNone_maskNoneconstanttagtokenizingshufFalse_lastEpoch.ckpt 
```
The three arguments `--transfer_learning`, `--model_name L_16`, and `--interm_features_fc` are crucial while the remaining is to be modified by yourself.
The training fits into the 8GB vram of my poor 3070 Ti Laptop GPU even at batch size 8 and is done fairly quickly due to the small size of the dataset. Note that testing is disabled by default. If you want to use test pass the argument `--use_test_set`. Validation will then be performed every `save_checkpoint_freq` epochs (default to 5).

### Inference

At this point we finally get a model to classify the characters of the series! To use it run
```
python classify_faces.py --dataset_path /path/to/classification_data_dir \
--checkpoint_path ../path/to/checkpoint_dir/trained_checkpoint_name.ckpt \
--src_dir /path/to/image_dir
```

The path of the classification dataset should be provided in order to read the class id mapping csv.
The images of `image_dir` should have the corresponding `.facedata.json` created in the [face detection section](#Face-Detection) (i.e. it should be the destination directory of `detect_faces.py`) as the face position data are used to create crops fed into the classifier.
Moreover, we also write the character information into `XXX.facedata.json`. At this point, `XXX.facedata.json` looks like
> {"n_faces": 3, "abs_pos": [[175, 150, 286, 265], [512, 209, 607, 307], [688, 134, 757, 249]], "rel_pos": [[0.1708984375, 0.2604166666666667, 0.279296875, 0.4600694444444444], [0.5, 0.3628472222222222, 0.5927734375, 0.5329861111111112], [0.671875, 0.2326388888888889, 0.7392578125, 0.4322916666666667]], "max_height_ratio": 0.1996527777777778, "characters": ["AobaKokona", "YukimuraAoi", "KuraueHinata"], "cropped": false}

(in contrast to ``"characters": ["unknown"]`` we just saw before)

#### Character _unknown_ and _ood_

How to deal with random person from anime that we are not interested in is a delicate question. You can see that I include a class _ood_ (out of distribution) above but this does not seem to be very effective. In consequence, I also set a confidence threshold 0.6 and if the probability of belonging to the classified class is lower than this threshold I set character to _unknown_. Both _unknown_ and _ood_ will be ignored in the following treatments.

#### Character folder creation

With the argument `--create_character_folder` the script also sorts the images and the `.metadata.json` files into their respective folder. Note it only add one level of folder to the current position of image, moving it from `/path/to/image_dir/2_faces/face_height_ratio_0-25/XXX.png` to `/path/to/image_dir/2_faces/face_height_ratio_0-25/chracter1+character2/XXX.png` .

_When I am writing this I notice that it does not move the tag files if they are already generated. A bug to be fixed later._

#### Manual inspection

At this point, or even before this, you may want to manually inspect the subfolders to be sure that things are in the good place. For example if you want to tag characters even from behind this can not be achieved with the current workflow as we do not see faces from behind (well I suppose). You can move things between folders to put them in the right place, as in the next step we can also use folder structure to generate the final metadata.


## Metadata Generation

## Folder Arrangement

## Get Ready for Training

## Using Fan Arts and Regularization Data