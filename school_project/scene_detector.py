import cv2
import numpy as np

# Threshold below which we consider frames to be from different scenes
# Higher values (closer to 1) mean more sensitive detection
SCENE_CHANGE_THRESHOLD = 0.9


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


def detect_scene_change(
    current_frame, previous_frame, threshold=SCENE_CHANGE_THRESHOLD
):
    """Detect scene change using multiple metrics.

    We use multiple complementary methods to make detection more robust:
    1. Histogram comparison - detects overall distribution changes
    2. Mean Absolute Difference - sensitive to sudden content changes
    3. Structural Similarity - focuses on structural changes

    Returns:
        bool: True if a scene change is detected, False otherwise
    """
    if previous_frame is None:
        return False

    # 1. Histogram comparison
    # Compare both color and grayscale histograms using correlation method
    # Correlation ranges from -1 to 1, where 1 means perfect match
    hist_gray_curr, hist_color_curr = calculate_frame_histogram(current_frame)
    hist_gray_prev, hist_color_prev = calculate_frame_histogram(previous_frame)

    correl_gray = cv2.compareHist(hist_gray_curr, hist_gray_prev, cv2.HISTCMP_CORREL)
    correl_color = cv2.compareHist(hist_color_curr, hist_color_prev, cv2.HISTCMP_CORREL)

    # 2. Mean Absolute Difference (MAD)
    # Measures average pixel-wise change between frames
    # Good for detecting sudden content changes
    curr_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
    prev_gray = cv2.cvtColor(previous_frame, cv2.COLOR_BGR2GRAY)
    mad = np.mean(np.abs(curr_gray.astype(float) - prev_gray.astype(float)))
    mad_normalized = mad / 255.0  # Normalize to [0,1] range

    # 3. Structural Similarity Index (SSIM)
    # Using histogram intersection as a simple approximation of structural similarity
    # Higher values indicate more similarity
    ssim = cv2.compareHist(hist_gray_curr, hist_gray_prev, cv2.HISTCMP_INTERSECT)
    ssim_normalized = ssim / np.sum(hist_gray_curr)

    # Weight the different metrics based on their reliability
    # Histograms get higher weight as they're more reliable for scene detection
    weights = {"correl_gray": 0.3, "correl_color": 0.3, "mad": 0.2, "ssim": 0.2}

    # Combine all metrics into a single similarity score
    # Higher score means more similar frames
    total_similarity = (
        weights["correl_gray"] * correl_gray
        + weights["correl_color"] * correl_color
        # Invert MAD since higher means less similar
        + weights["mad"] * (1 - mad_normalized)
        + weights["ssim"] * ssim_normalized
    )

    # Use both static and dynamic thresholds
    # Dynamic threshold adjusts based on motion (MAD) to reduce false positives
    # during high-motion scenes
    static_threshold = threshold
    dynamic_threshold = threshold * (1 + mad_normalized * 0.2)

    return total_similarity < min(static_threshold, dynamic_threshold)
