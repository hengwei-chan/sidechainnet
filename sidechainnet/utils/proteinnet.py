""" This script allows the raw ProteinNet files from
https://github.com/aqlaboratory/proteinnet. """
import itertools
import os
from glob import glob
import multiprocessing

import torch


def load_ids_from_text_files(directory, training_set):
    """
    Given a directory where raw ProteinNet records are stored along with .ids
    files, reads and returns the contents of those files. Effectively returns
    a list of IDs associated with the training, validation, and test sets.
    """
    with open(os.path.join(directory, f"training_{training_set}_ids.txt"), "r") as trainf, \
            open(os.path.join(directory, "validation_ids.txt"), "r") as validf, \
            open(os.path.join(directory, "testing_ids.txt"), "r") as testf:
        train_ids = trainf.read().splitlines()
        valid_ids = validf.read().splitlines()
        test_ids = testf.read().splitlines()
        return train_ids, valid_ids, test_ids


def read_protein_from_file(file_pointer, include_tertiary):
    """
    Modified from github.com/OpenProtein/openprotein:preprocessing.py on June
    20, 2019. Original carries an MIT license. Copyright (c) 2018 Jeppe
    Hallgren.
    """
    dict_ = {}
    _dssp_dict = {'L': 0, 'H': 1, 'B': 2, 'E': 3, 'G': 4, 'I': 5, 'T': 6, 'S': 7}
    _mask_dict = {'-': 0, '+': 1}

    while True:
        next_line = file_pointer.readline()
        if next_line == '[ID]\n':
            id_ = file_pointer.readline()[:-1]
            dict_.update({'id': id_})
        elif next_line == '[PRIMARY]\n':
            primary = file_pointer.readline()[:-1]
            dict_.update({'primary': primary})
        elif next_line == '[EVOLUTIONARY]\n':
            evolutionary = []
            for residue in range(21): evolutionary.append(
                [float(step) for step in file_pointer.readline().split()])
            dict_.update({'evolutionary': evolutionary})
        elif next_line == '[SECONDARY]\n':
            secondary = list([_dssp_dict[dssp] for dssp in file_pointer.readline()[:-1]])
            dict_.update({'secondary': secondary})
        elif next_line == '[TERTIARY]\n' and include_tertiary:
            tertiary = []
            # 3 dimension
            for axis in range(3): tertiary.append(
                [float(coord) for coord in file_pointer.readline().split()])
            dict_.update({'tertiary': tertiary})
        elif next_line == '[MASK]\n':
            mask = list([_mask_dict[aa] for aa in file_pointer.readline()[:-1]])
            dict_.update({'mask': mask})
        elif next_line == '\n':
            return dict_
        elif next_line == '':
            return None


def process_file(input_filename_out_dir, return_ids=True):
    """
    A parallelizable method for processing one raw ProteinNet file and
    creating a PyTorch-saved python dictionary of the data.
    """
    all_ids = []
    input_filename, out_dir = input_filename_out_dir
    print("    " + input_filename)
    text_file = open(os.path.join(out_dir, os.path.basename(input_filename) + '_ids.txt'), "w")
    input_file = open(input_filename, "r")
    meta_dict = {}
    while True:
        next_protein = read_protein_from_file(input_file, include_tertiary=True)
        if next_protein is None:
            break
        id_ = next_protein["id"]
        del next_protein["id"]
        meta_dict.update({id_: next_protein})
        text_file.write(f"{id_}\n")
        if return_ids:
            all_ids.append(id_)
    torch.save(meta_dict, os.path.join(out_dir, os.path.basename(input_filename) + ".pt"))
    input_file.close()
    text_file.close()
    print(f"{input_filename} finished.")
    if return_ids:
        return (input_filename, all_ids)


class ProteinNet(object):
    """
    Defines a wrapper for interacting with a ProteinNet dataset.
    """

    def __init__(self, raw_dir, training_set):
        self.raw_dir = raw_dir
        self.training_set = training_set

    def parse_raw_data(self):
        input_files = glob(os.path.join(self.raw_dir, "raw/*[!.ids]"))


def parse_raw_proteinnet(proteinnet_in_dir, proteinnet_out_dir, training_set):
    """Extracts and saves information for a single ProteinNet dataset.

    Preprocesses raw ProteinNet records by reading them and transforming them
    into PyTorch-saved dictionaries. Files are kept separate due to file size.
    For ease of inspection, the ProteinNet IDs are extracted and save as `.ids`
    files.
    # TODO: assert existence of test/targets files

    Args:
        proteinnet_in_dir: Directory where all raw ProteinNet files are kept
        proteinnet_out_dir: Directory to save processed data
        training_set: Which thinning of ProteinNet is requested

    Returns:
        relevant_ids: A list of ProteinNet IDs from corresponding training_set

    """
    train_file = f"training_{training_set}.pt"

    # If the desired ProteinNet dataset has already been processed, load its IDs
    if os.path.exists(os.path.join(proteinnet_out_dir, train_file)):
        print(f"Raw ProteinNet files already preprocessed ({os.path.join(proteinnet_out_dir, train_file)}).")
        relevant_ids_file = os.path.join(proteinnet_out_dir, train_file.replace(".pt", "_ids.txt"))
        with open(relevant_ids_file, "r") as f:
            relevant_ids = f.read().splitlines()
        return relevant_ids

    # If the torch-preprocessed ProteinNet dictionaries don't exist, create them.
    if not os.path.exists(proteinnet_out_dir):
        os.mkdir(proteinnet_out_dir)

    # Look for the raw ProteinNet files
    input_files = glob(os.path.join(proteinnet_in_dir, "*[!.ids]"))
    assert len(input_files) == 8, f"Looking for raw ProteinNet files in '{proteinnet_in_dir}', but could not find " \
                                  f"all 8.\n Please download from Mohammed AlQuraishi's repository: " \
                                  f"https://github.com/aqlaboratory/proteinnet"

    # Process each ProteinNet file by turning them into PyTorch saved dictionaries
    print("Preprocessing raw ProteinNet files...")
    with multiprocessing.Pool(multiprocessing.cpu_count()) as p:
        file_pnids = p.map(process_file, zip(input_files, itertools.repeat(proteinnet_out_dir)))
    print("Done.")

    # Return the ProteinNet IDs associated with the target dataset
    relevant_ids = next(filter(lambda r: f"training_{training_set}" in r[0], file_pnids))
    return relevant_ids