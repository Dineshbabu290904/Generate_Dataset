import streamlit as st
import cv2
import os
import requests
import mediapipe as mp
import time
import base64
import logging

# Set up logging to log to a file and to the console
logging.basicConfig(filename='dataset_generator.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

mp_face_mesh = mp.solutions.face_mesh


def upload_bulk_to_github(files_data, repo, branch, token):
    """
    Uploads a list of files to GitHub in bulk, creating a single commit.
    """
    try:
        url = f'https://api.github.com/repos/{repo}/contents/'
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }

        commits = []
        for file_path, repo_path in files_data:
            with open(file_path, 'rb') as file:
                content = file.read()
            encoded_content = base64.b64encode(content).decode('utf-8')

            file_url = f'{url}{repo_path}'
            response = requests.get(file_url, headers=headers)
            if response.status_code == 200:
                file_sha = response.json()['sha']
                commit_data = {
                    'message': f'Update {repo_path}',
                    'content': encoded_content,
                    'branch': branch,
                    'sha': file_sha
                }
            else:
                commit_data = {
                    'message': f'Add {repo_path}',
                    'content': encoded_content,
                    'branch': branch
                }

            commits.append((repo_path, commit_data))

        for repo_path, commit_data in commits:
            response = requests.put(f"{url}{repo_path}", headers=headers, json=commit_data)
            if response.status_code in [200, 201]:
                logging.info(f"Successfully uploaded/updated {repo_path}")
            else:
                logging.error(f"Failed to upload {repo_path}: {response.json()}")

    except Exception as e:
        logging.error(f"Error uploading files in bulk: {e}")


def capture_images(roll_number, num_images, direction, temp_path, repo, branch, token):
    """
    Captures images from the webcam, stores them locally in a temporary folder,
    uploads them to GitHub in bulk, and deletes them after uploading.
    """
    try:
        cap = cv2.VideoCapture(0)
        frame_placeholder = st.empty()
        count = 0
        image_paths = []

        while cap.isOpened() and count < num_images:
            ret, frame = cap.read()
            if not ret:
                logging.warning("Video Capture Ended")
                break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_placeholder.image(rgb_frame, channels="RGB")
            with mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1) as face_mesh:
                results = face_mesh.process(rgb_frame)

                if results.multi_face_landmarks:
                    image_name = f'{roll_number}_{direction}_{count}.jpg'
                    local_image_path = os.path.join(temp_path, image_name)
                    cv2.imwrite(local_image_path, frame)
                    image_paths.append(local_image_path)
                    count += 1
                    time.sleep(0.5)

        cap.release()
        cv2.destroyAllWindows()

        files_data = [(path, f'{roll_number}/{direction}/{os.path.basename(path)}') for path in image_paths]
        upload_bulk_to_github(files_data, repo, branch, token)

        for path in image_paths:
            os.remove(path)
        logging.info("All captured images deleted after upload.")

    except Exception as e:
        logging.error(f"Error during image capture: {e}")


def main():
    st.title("Face Dataset Generator")

    roll_number = st.text_input("Enter Roll Number")
    name = st.text_input("Enter Student Name")
    repo = st.secrets["Repo"]
    branch = st.secrets["Branch"]
    token = st.secrets["TOKEN"]

    if st.button("Start Capture"):
        if not roll_number or not name or not repo or not branch or not token:
            st.error("Please enter all required fields.")
            return

        try:
            temp_path = '/tmp/temp_images'
            os.makedirs(temp_path, exist_ok=True)

            capture_images(roll_number, 50, 'front', temp_path, repo, branch, token)
            capture_images(roll_number, 25, 'left', temp_path, repo, branch, token)
            capture_images(roll_number, 25, 'right', temp_path, repo, branch, token)

            st.success(f"Dataset for {roll_number}_{name} captured and uploaded successfully!")
            os.rmdir(temp_path)

        except Exception as e:
            st.error(f"Error: {e}")


if __name__ == '__main__':
    main()
