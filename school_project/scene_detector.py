import cv2
import numpy as np


def calculate_frame_histogram(frame):
    """Calculate histogram of a frame.

    We calculate both grayscale and color histograms because:
    1. Grayscale is good for detecting structural/brightness changes
    2. Color histogram helps detect major color palette changes between scenes
    """
    # Convert to grayscale for structural analysis
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Create grayscale histogram with 64 bins for efficiency
    # Fewer bins help smooth out minor variations while keeping important features
    hist_gray = cv2.calcHist([gray], [0], None, [64], [0, 256])

    # Create 3D color histogram with 8 bins per channel
    # This gives us 8x8x8=512 bins, capturing color distribution without too much detail
    hist_color = cv2.calcHist(
        [frame], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256]
    )

    # Normalize histograms to make them scale-invariant
    cv2.normalize(hist_gray, hist_gray)
    cv2.normalize(hist_color, hist_color)

    return hist_gray, hist_color


def calculate_frame_similarity(current_frame, previous_frame):
    """Calculate similarity between frames, returns value between 0 and 1.

    Higher value means frames are more similar.
    """
    if previous_frame is None:
        return 1.0

    hist_gray_curr, hist_color_curr = calculate_frame_histogram(current_frame)
    hist_gray_prev, hist_color_prev = calculate_frame_histogram(previous_frame)

    correl_gray = cv2.compareHist(hist_gray_curr, hist_gray_prev, cv2.HISTCMP_CORREL)
    correl_color = cv2.compareHist(hist_color_curr, hist_color_prev, cv2.HISTCMP_CORREL)

    curr_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
    prev_gray = cv2.cvtColor(previous_frame, cv2.COLOR_BGR2GRAY)
    mad = np.mean(np.abs(curr_gray.astype(float) - prev_gray.astype(float)))
    mad_normalized = mad / 255.0

    ssim = cv2.compareHist(hist_gray_curr, hist_gray_prev, cv2.HISTCMP_INTERSECT)
    ssim_normalized = ssim / np.sum(hist_gray_curr)

    identical_regions_score = detect_identical_regions(current_frame, previous_frame)

    weights = {
        "correl_gray": 0.2,
        "correl_color": 0.2,
        "mad": 0.2,
        "ssim": 0.2,
        "identical_regions": 0.2,
    }

    total_similarity = (
        weights["correl_gray"] * correl_gray
        + weights["correl_color"] * correl_color
        + weights["mad"] * (1 - mad_normalized)
        + weights["ssim"] * ssim_normalized
        + weights["identical_regions"] * identical_regions_score
    )

    # Dynamic ratio for MAD to reduce false positives during high-motion scenes
    mad_ratio = 0.2
    mad_correction = 1 + mad_normalized * mad_ratio

    return total_similarity * mad_correction


def detect_identical_regions(current_frame, previous_frame):
    """Detect identical regions between two frames.

    Returns:
        float: Score in the range 0-1, where 1 means more identical areas
    """
    # Create mask of identical pixels
    diff = cv2.absdiff(current_frame, previous_frame)
    mask = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    identical_pixels = cv2.threshold(mask, 1, 255, cv2.THRESH_BINARY_INV)[1]

    # Use morphological operations to remove noise
    kernel = np.ones((3, 3), np.uint8)
    identical_pixels = cv2.morphologyEx(identical_pixels, cv2.MORPH_CLOSE, kernel)

    # Find connected components (potential logos or other identical areas)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        identical_pixels
    )

    # Calculate total area of identical areas (ignore small areas)
    total_area = 0
    min_area = 100  # Minimum area in pixels
    for i in range(1, num_labels):  # Start from 1, as 0 is background
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            total_area += stats[i, cv2.CC_STAT_AREA]

    # Normalize by frame area
    frame_area = current_frame.shape[0] * current_frame.shape[1]
    similarity_score = total_area / frame_area

    return similarity_score
