import numpy as np
import cv2
import base64
import re
from io import BytesIO
import logging
import os
import json

logger = logging.getLogger(__name__)

# Load the pre-trained face detector from OpenCV
face_cascade_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
face_cascade = cv2.CascadeClassifier(face_cascade_path)

def process_image_data(image_data):
    """Process the base64 image data and return a numpy array"""
    try:
        # Remove the "data:image/jpeg;base64," part if present
        if 'base64' in image_data:
            image_data = re.sub('^data:image/.+;base64,', '', image_data)
        
        # Decode base64 string to bytes
        image_bytes = base64.b64decode(image_data)
        
        # Convert bytes to numpy array
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        
        # Decode the numpy array as an image
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        
        return image
    
    except Exception as e:
        logger.error(f"Error processing image data: {str(e)}")
        return None

def detect_face(image):
    """Detect face in the image using OpenCV's cascade classifier"""
    try:
        # Convert to grayscale for face detection
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply histogram equalization to improve contrast
        gray = cv2.equalizeHist(gray)
        
        # Detect faces with more strict parameters
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=8,  # Increased for stricter detection
            minSize=(80, 80)  # Increased minimum face size
        )
        
        return faces
    except Exception as e:
        logger.error(f"Error detecting face: {str(e)}")
        return []

def extract_face_features(image, face):
    """Extract features from a face region"""
    try:
        x, y, w, h = face
        
        # Add more margin to capture full face
        margin = int(0.2 * w)  # 20% margin
        x = max(0, x - margin)
        y = max(0, y - margin)
        w = min(image.shape[1] - x, w + 2*margin)
        h = min(image.shape[0] - y, h + 2*margin)
        
        face_img = image[y:y+h, x:x+w]
        
        # Higher resolution for better feature extraction
        face_img = cv2.resize(face_img, (200, 200))
        
        # Convert to grayscale
        gray_face = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        
        # Enhance contrast
        gray_face = cv2.equalizeHist(gray_face)
        
        # Apply Gaussian blur to reduce noise
        gray_face = cv2.GaussianBlur(gray_face, (5, 5), 0)
        
        # Use LBP (Local Binary Patterns) for more accurate face recognition
        # Create LBPH extractor
        radius = 2
        neighbors = 8
        grid_x = 8
        grid_y = 8
        
        # Manual LBP feature extraction for better control
        lbp_face = np.zeros_like(gray_face)
        
        # For each pixel, compare with neighbors and create binary pattern
        rows, cols = gray_face.shape
        for i in range(radius, rows-radius):
            for j in range(radius, cols-radius):
                center = gray_face[i, j]
                binary = 0
                
                # Check all neighbors in clockwise order
                if gray_face[i-radius, j-radius] >= center: binary |= 1 << 0
                if gray_face[i-radius, j] >= center: binary |= 1 << 1
                if gray_face[i-radius, j+radius] >= center: binary |= 1 << 2
                if gray_face[i, j+radius] >= center: binary |= 1 << 3
                if gray_face[i+radius, j+radius] >= center: binary |= 1 << 4
                if gray_face[i+radius, j] >= center: binary |= 1 << 5
                if gray_face[i+radius, j-radius] >= center: binary |= 1 << 6
                if gray_face[i, j-radius] >= center: binary |= 1 << 7
                
                lbp_face[i, j] = binary
        
        # Create histogram for each region
        block_size_x = cols // grid_x
        block_size_y = rows // grid_y
        
        histograms = []
        for i in range(grid_y):
            for j in range(grid_x):
                block = lbp_face[i*block_size_y:(i+1)*block_size_y, j*block_size_x:(j+1)*block_size_x]
                hist, _ = np.histogram(block, bins=256, range=(0, 256), density=True)
                histograms.extend(hist)
        
        # Also add HOG features for additional discrimination
        hog = cv2.HOGDescriptor((200, 200), (20, 20), (10, 10), (10, 10), 9)
        hog_features = hog.compute(gray_face).flatten()
        
        # Combine LBP and HOG features
        combined_features = np.concatenate((np.array(histograms), hog_features))
        
        return combined_features
    except Exception as e:
        logger.error(f"Error extracting face features: {str(e)}")
        return None

def process_and_encode_face(image_data):
    """Process the image data and return the face features"""
    try:
        # Process the image data
        image = process_image_data(image_data)
        if image is None:
            logger.error("Failed to process image data")
            return None
        
        # Detect faces
        faces = detect_face(image)
        
        # If no face or multiple faces detected, return None
        if len(faces) != 1:
            logger.warning(f"Expected exactly 1 face, but found {len(faces)} faces")
            return None
        
        # Extract features from the face
        face_features = extract_face_features(image, faces[0])
        
        if face_features is None:
            logger.error("Failed to extract face features")
            return None
            
        # Normalize the feature vector (important for consistent comparisons)
        face_features = face_features / np.linalg.norm(face_features)
        
        return face_features
    
    except Exception as e:
        logger.error(f"Error encoding face: {str(e)}")
        return None

def compare_face_features(face_features1, face_features2, tolerance=0.75):
    """
    Compare two face features and determine if they match
    
    Higher tolerance = stricter matching (requires closer match)
    This is a similarity score between 0 and 1, where 1 is a perfect match
    """
    try:
        if face_features1 is None or face_features2 is None:
            return False
            
        # Ensure features are normalized
        if np.linalg.norm(face_features1) > 0:
            face_features1 = face_features1 / np.linalg.norm(face_features1)
        if np.linalg.norm(face_features2) > 0:
            face_features2 = face_features2 / np.linalg.norm(face_features2)
            
        # Compute cosine similarity (dot product of normalized vectors)
        similarity = np.dot(face_features1, face_features2)
        
        # Log the similarity for debugging purposes
        logger.info(f"Face comparison similarity: {similarity} (threshold: {tolerance})")
        
        # Return True if similarity is above threshold
        return similarity > tolerance
    except Exception as e:
        logger.error(f"Error comparing faces: {str(e)}")
        return False

def recognize_faces(image_data, known_encodings, known_ids, tolerance=0.75):
    """
    Recognize faces in the image and return the IDs of recognized students
    
    Args:
        image_data: Base64 encoded image data
        known_encodings: List of known face encodings (features)
        known_ids: List of corresponding student IDs
        tolerance: Face recognition similarity threshold (higher = stricter matching)
        
    Returns:
        List of recognized student IDs
    """
    try:
        if not known_encodings or not known_ids:
            logger.warning("No known encodings or IDs provided")
            return []
        
        # Process the image data
        image = process_image_data(image_data)
        if image is None:
            logger.error("Failed to process image data")
            return []
        
        # Detect faces
        faces = detect_face(image)
        
        # If no faces detected, return empty list
        if len(faces) == 0:
            logger.warning("No faces detected in the image")
            return []
        
        recognized_ids = []
        similarities = {}  # Track similarities for logging
        
        # Check each face in the image
        for face in faces:
            # Extract features
            face_features = extract_face_features(image, face)
            if face_features is None:
                logger.warning("Failed to extract features from detected face")
                continue
            
            # Normalize the feature vector
            if np.linalg.norm(face_features) > 0:
                face_features = face_features / np.linalg.norm(face_features)
            
            # Compare with known encodings
            for i, known_encoding in enumerate(known_encodings):
                # Compute similarity
                if np.linalg.norm(known_encoding) > 0:
                    known_encoding_norm = known_encoding / np.linalg.norm(known_encoding)
                else:
                    known_encoding_norm = known_encoding
                
                similarity = np.dot(face_features, known_encoding_norm)
                similarities[known_ids[i]] = similarity
                
                if similarity > tolerance:
                    recognized_ids.append(known_ids[i])
                    break
        
        # Log all similarities for troubleshooting
        if similarities:
            logger.info(f"Face match similarities: {similarities}")
            if not recognized_ids:
                logger.info(f"No matches found with tolerance {tolerance}. Highest similarity: {max(similarities.values())}")
        
        return recognized_ids
    
    except Exception as e:
        logger.error(f"Error recognizing faces: {str(e)}")
        return []