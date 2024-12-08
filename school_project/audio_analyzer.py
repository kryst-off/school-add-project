import numpy as np
import librosa
from scipy.spatial.distance import euclidean


def extract_mfcc(audio_data, sample_rate):
    """
    Extracts MFCC features from raw audio data.

    :param audio_data: Numpy array of raw audio data
    :param sample_rate: Sampling rate of the audio data
    :return: Numpy array of MFCC features
    """
    mfccs = librosa.feature.mfcc(y=audio_data, sr=sample_rate, n_mfcc=13)
    # Compute the mean MFCC across time frames
    mfccs_mean = np.mean(mfccs.T, axis=0)
    return mfccs_mean


def compare_audio_features(mfcc1, mfcc2):
    """
    Compares two sets of MFCC features using Euclidean distance.

    :param mfcc1: Numpy array of MFCC features from first audio segment
    :param mfcc2: Numpy array of MFCC features from second audio segment
    :return: Float value representing the distance (smaller means more similar)
    """
    distance = euclidean(mfcc1, mfcc2)
    return distance


def decode_audio_packets(packets):
    """
    Decode audio packets into a numpy array.

    :param packets: Iterable of av.AudioPacket
    :return: Numpy array of decoded audio data
    """
    audio_chunks = []
    for packet in packets:
        for frame in packet.decode():
            audio_chunks.append(frame.to_ndarray().flatten())
    return np.concatenate(audio_chunks) if audio_chunks else np.array([])


def are_scenes_audio_similar(packets1, packets2, sample_rate=44100, threshold=80):
    """
    Determines if two audio segments are similar based on their audio content.

    :param packets1: Iterable of av.AudioPacket for the first audio segment
    :param packets2: Iterable of av.AudioPacket for the second audio segment
    :param sample_rate: Sampling rate for audio decoding
    :param threshold: Distance threshold below which audio segments are considered similar
    :return: Boolean indicating if the audio segments are similar
    """
    # Decode audio packets
    audio_data1 = decode_audio_packets(packets1)
    audio_data2 = decode_audio_packets(packets2)

    # Ensure audio data is not empty
    if audio_data1.size == 0 or audio_data2.size == 0:
        return False

    # Extract MFCC features
    mfcc1 = extract_mfcc(audio_data1.astype(float), sample_rate)
    mfcc2 = extract_mfcc(audio_data2.astype(float), sample_rate)

    # Compare features
    distance = compare_audio_features(mfcc1, mfcc2)

    print(f"Distance: {distance}")

    # Determine similarity based on threshold
    return distance < threshold
