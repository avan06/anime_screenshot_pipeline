import argparse
import os
import json
import random

from tqdm import tqdm
from pathlib import Path

from danbooru_tag_tree.tag_tree import TagTree


def get_files_recursively(folder_path):
    allowed_patterns = [
        '*.[Pp][Nn][Gg]', '*.[Jj][Pp][Gg]', '*.[Jj][Pp][Ee][Gg]',
        '*.[Gg][Ii][Ff]', '*.[Ww][Ee][Bb][Pp]',
    ]

    image_path_list = [
        str(path) for pattern in allowed_patterns
        for path in Path(folder_path).rglob(pattern)
    ]

    return image_path_list


def parse_facepos(facepos_info):
    descrs = []
    for facepos in facepos_info:
        # For legacy
        if isinstance(facepos, str):
            components = facepos.split(' ')
            top = int(components[1]) / 100
            bottom = int(components[2]) / 100
            left = int(components[4]) / 100
            right = int(components[5]) / 100
        else:
            left, top, right, bottom = facepos
        cx = (left + right) / 2
        # cy = (top + bottom) / 2
        if cx < 0.38:
            posh = 'at left'
        elif cx < 0.62:
            posh = 'in the middle'
        else:
            posh = 'at right'
        # if cy < 0.2:
        #     posv = 'fvtp'
        # elif cy < 0.4:
        #     posv = 'fvmt'
        # elif cy < 0.6:
        #     posv = 'fvmd'
        # elif cy < 0.8:
        #     posv = 'fvmb'
        # else:
        #     posv = 'fvbt'
        descrs.append(f'{posh}')
    return ' '.join(descrs)


def dict_to_caption(info_dict, attire_list, args):
    caption = ""
    sep_string = args.separator + " "
    characters = None
    if random.random() < args.use_npeople_prob and 'n_people' in info_dict:
        count = info_dict['n_people']
        suffix = 'person' if count == 1 else 'people'
        caption += f'{count}{suffix}'
    if (random.random() < args.use_character_prob):
        if 'character' in info_dict:
            characters = info_dict['character']
        elif 'characters' in info_dict:
            characters = info_dict['characters']
        if characters is not None:
            for to_remove in ['unknown', 'ood']:
                characters = list(filter(
                    lambda item: item != to_remove, characters))
            if len(characters) > 0:
                if caption != "":
                    caption += sep_string
                caption += sep_string.join(characters)
    if random.random() < args.use_copyright_prob and 'copyright' in info_dict:
        copyright = info_dict['copyright']
        copyright = list(filter(
            lambda item: item != 'unknown', copyright))
        if len(copyright) > 0:
            if caption != "":
                caption += sep_string
            caption += 'from ' + ' '.join(copyright)
    if random.random() < args.use_general_prob and 'general' in info_dict:
        if caption != "":
            caption += sep_string
        caption += info_dict['general']
    if random.random() < args.use_artist_prob and 'artist' in info_dict:
        artist = info_dict['artist']
        artist = list(filter(
                lambda item: item != 'anonymous', artist))
        if len(artist) > 0:
            if caption != "":
                caption += sep_string
            caption += 'by ' + ' '.join(artist)
    if random.random() < args.use_rating_prob and 'rating' in info_dict:
        if info_dict['rating'] == 'explicit':
            if caption != "":
                caption += sep_string
            caption += 'explicit'
    if random.random() < args.use_facepos_prob and 'facepos' in info_dict:
        facepos_info = info_dict['facepos']
        if len(facepos_info) > 0:
            if caption != "":
                caption += sep_string
            caption += parse_facepos(facepos_info)
    if random.random() < args.use_tags_prob and 'tags' in info_dict:
        has_outfit = False
        if characters is not None:
            has_outfit = True
            for character in characters:
                if ',' not in character:
                    has_outfit = False
        tags, tracen = process_tags(
            info_dict['tags'], has_outfit, attire_list, args)
        if tracen and characters is not None and len(characters) == 1:
            character = characters[0].split(',')[0]
            character = character + ', ' + 'tracen school uniform'
            caption = caption.replace(characters[0], character)
            tags.remove('tracen_school_uniform')
        if len(tags) > 0:
            if caption != "":
                caption += sep_string
            caption += ', '.join(tags)
    return caption.replace('_', ' ')


def process_tags(tags, has_outfit, attire_list, args):
    new_tags = []
    general_tags = []
    has_tracen_school_uniform = False
    blacklist = ['parody']
    for tag in tags:
        if 'boy' in tag or 'girl' in tag or 'solo' in tag:
            general_tags.append(tag)
        elif tag == 'tracen_school_uniform':
            has_tracen_school_uniform = True
            general_tags.append(tag)
        elif ('hair' in tag
                or 'ponytail' in tag
                or 'twintail' in tag
                or 'braid' in tag
                or 'bun' in tag
                or 'bangs' in tag
                or 'ahoge' in tag):
            if not args.drop_hair_tag:
                new_tags.append(tag)
        elif 'eyes' in tag:
            if not args.drop_eye_tag:
                new_tags.append(tag)
        elif has_outfit and tag.replace('_', ' ') in attire_list:
            if not args.drop_outfit_tag:
                new_tags.append(tag)
        elif tag not in blacklist:
            new_tags.append(tag)
    if args.shuffle_tags:
        random.shuffle(new_tags)
    tags = general_tags + new_tags
    tags = tags[:args.max_tag_number]
    return tags, has_tracen_school_uniform


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("--src_dir", type=str, help="directory to load images")
    parser.add_argument("--separator", type=str, default=',')
    parser.add_argument("--output_ext", type=str, default='.txt')
    parser.add_argument('--use_npeople_prob', type=float, default=0)
    parser.add_argument('--use_character_prob', type=float, default=1)
    parser.add_argument('--use_general_prob', type=float, default=1)
    parser.add_argument('--use_copyright_prob', type=float, default=0)
    parser.add_argument('--use_artist_prob', type=float, default=1)
    parser.add_argument('--use_rating_prob', type=float, default=1)
    parser.add_argument('--use_facepos_prob', type=float, default=0)
    parser.add_argument('--use_tags_prob', type=float, default=1)
    parser.add_argument('--max_tag_number', type=int, default=15)
    parser.add_argument('--shuffle_tags', action='store_true')
    parser.add_argument('--drop_hair_tag', action='store_true')
    parser.add_argument('--drop_eye_tag', action='store_true')
    parser.add_argument('--drop_outfit_tag', action='store_true')
    args = parser.parse_args()

    if args.drop_outfit_tag:
        tree = TagTree()
        tree.build_from_json('danbooru_tag_tree/tag_tree.json')
        attire_list = tree.get_tags('Attire', reverse_query=True)
    else:
        attire_list = []

    files = get_files_recursively(args.src_dir)
    for file in tqdm(files):
        filename_noext = os.path.splitext(file)[0]
        with open(filename_noext + '.json', 'r') as f:
            info_dict = json.load(f)
        caption = dict_to_caption(info_dict, attire_list, args)
        with open(filename_noext + args.output_ext, 'w') as f:
            f.write(caption)
