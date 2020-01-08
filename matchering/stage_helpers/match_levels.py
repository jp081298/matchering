import numpy as np

from ..log import debug
from .. import MainConfig
from ..utils import to_db
from ..dsp import lr_to_ms, size, unfold, batch_rms, rms


def normalize_reference(
        reference: np.ndarray,
        config: MainConfig
) -> (np.ndarray, float):
    debug('Normalizing the REFERENCE...')
    reference_max_value = np.abs(reference).max()
    final_amplitude_coefficient = 1.
    if reference_max_value >= config.threshold:
        debug('The REFERENCE was not changed. There is no final amplitude coefficient')
    else:
        final_amplitude_coefficient = max(config.min_value, reference_max_value / config.threshold)
        reference /= final_amplitude_coefficient
        debug(f'The REFERENCE was normalized. '
              f'Final amplitude coefficient for the TARGET audio is: {to_db(final_amplitude_coefficient)}')
    return reference, final_amplitude_coefficient


def __calculate_piece_sizes(
        array: np.ndarray,
        max_piece_size: int,
        name: str,
        sample_rate: int,
) -> (int, int, int):
    array_size = size(array)
    divisions = int(array_size / max_piece_size) + 1
    debug(f'The {name} will be didived into {divisions} pieces')
    piece_size = int(array_size / divisions)
    debug(f'One piece of the {name} has a length of {piece_size} samples or {piece_size / sample_rate:.2f} seconds')
    return array_size, divisions, piece_size


def get_lpis_and_match_rms(
        rmses: np.ndarray,
        average_rms: float,
) -> (np.ndarray, float):
    loudest_piece_idxs = np.where(rmses >= average_rms)
    loudest_rmses = rmses[loudest_piece_idxs]
    match_rms = rms(loudest_rmses)
    debug(f'The current average RMS value in the loudest pieces is {to_db(match_rms)}')
    return loudest_piece_idxs, match_rms


def __extract_loudest_pieces(
        rmses: np.ndarray,
        average_rms: float,
        unfolded_mid: np.ndarray,
        unfolded_side: np.ndarray,
        name: str,
) -> (np.ndarray, np.ndarray, float):
    debug(f'Extracting the loudest pieces of the {name} audio '
          f'with the RMS value more than average {to_db(average_rms)}...')

    loudest_piece_idxs, match_rms = get_lpis_and_match_rms(rmses, average_rms)

    mid_loudest_pieces = unfolded_mid[loudest_piece_idxs]
    side_loudest_pieces = unfolded_side[loudest_piece_idxs]
    return mid_loudest_pieces, side_loudest_pieces, match_rms


def get_average_rms(
        array: np.ndarray,
        piece_size: int,
        divisions: int,
        name: str
) -> (np.ndarray, np.ndarray, float):
    name = name.upper()
    unfolded_array = unfold(array, piece_size, divisions)
    debug(f'Calculating RMSes of the {name} pieces...')
    rmses = batch_rms(unfolded_array)
    average_rms = rms(rmses)
    return unfolded_array, rmses, average_rms


def analyze_levels(
        array: np.ndarray,
        name: str,
        config: MainConfig,
) -> (np.ndarray, np.ndarray, np.ndarray, np.ndarray, float, float, float):
    name = name.upper()  # <--

    debug(f'Calculating mid and side channels of the {name}...')
    mid, side = lr_to_ms(array)
    del array

    array_size, divisions, piece_size = __calculate_piece_sizes(
        mid,
        config.max_piece_size,
        name,
        config.internal_sample_rate
    )

    unfolded_mid, rmses, average_rms = get_average_rms(mid, piece_size, divisions, name)
    unfolded_side = unfold(side, piece_size, divisions)

    mid_loudest_pieces, side_loudest_pieces, match_rms = __extract_loudest_pieces(
        rmses,
        average_rms,
        unfolded_mid,
        unfolded_side,
        name
    )

    return mid, side, mid_loudest_pieces, side_loudest_pieces, match_rms, divisions, piece_size
