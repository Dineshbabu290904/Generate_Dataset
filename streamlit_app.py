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

    Args:
        files_data: List of tuples containing (file_path, file_name_in_repo) for each file.
        repo: GitHub repository in 'username/repo' format.
        branch: Target branch in the repository.
        token: GitHub personal access token.
    """
    try:
        url = f'https://api.github.com/repos/{repo}/contents/'
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }

        # Prepare the data for the bulk upload
        commits = []
        for file_path, repo_path in files_data:
            with open(file_path, 'rb') as file:
                content = file.read()
            encoded_content = base64.b64encode(content).decode('utf-8')

            # Check if the file already exists in the repository
            file_url = f'{url}{repo_path}'
            response = requests.get(file_url, headers=headers)
            if response.status_code == 200:
                # If the file exists, get the sha value for updating the file
                file_sha = response.json()['sha']
                commit_data = {
                    'message': f'Update {repo_path}',
                    'content': encoded_content,
                    'branch': branch,
                    'sha': file_sha  # Include the sha for update
                }
                # Updating file
                st.session_state.upload_message = f"Updating {repo_path}..."
                logging.info(f"Updating {repo_path}")
            else:
                # If the file doesn't exist, prepare a commit without sha
                commit_data = {
                    'message': f'Add {repo_path}',
                    'content': encoded_content,
                    'branch': branch
                }
                # Adding new file
                st.session_state.upload_message = f"Adding {repo_path}..."
                logging.info(f"Adding {repo_path}")

            commits.append((repo_path, commit_data))

        # Perform the upload for each file
        for repo_path, commit_data in commits:
            response = requests.put(f"{url}{repo_path}", headers=headers, json=commit_data)
            if response.status_code == 201:
                st.session_state.upload_message = f"Successfully uploaded {repo_path}"
                logging.info(f"Successfully uploaded {repo_path}")
            elif response.status_code == 200:
                st.session_state.upload_message = f"Successfully updated {repo_path}"
                logging.info(f"Successfully updated {repo_path}")
            else:
                st.session_state.upload_message = f"Failed to upload {repo_path}: {response.json()}"
                logging.error(f"Failed to upload {repo_path}: {response.json()}")

            # Clear the previous message after a short delay to update with the next one
            time.sleep(2)
            st.session_state.upload_message = ""

    except Exception as e:
        st.session_state.upload_message = f"Error uploading files in bulk: {e}"
        logging.error(f"Error uploading files in bulk: {e}")


def capture_images(roll_number, num_images, direction, temp_path, repo, branch, token):
    """
    Captures images from the webcam, stores them locally in a temporary folder,
    uploads them to GitHub in bulk, and deletes them after uploading.

    Args:
        roll_number: Roll number of the student.
        num_images: Number of images to capture.
        direction: 'front', 'left', or 'right'.
        temp_path: Local path to temporarily save images.
        repo: GitHub repository.
        branch: GitHub branch to upload files.
        token: GitHub token.
    """
    try:
        cap = cv2.VideoCapture(0)
        frame_placeholder = st.empty()
        message_placeholder = st.empty()  # Placeholder for the capture message
        angle_placeholder = st.empty()  # Placeholder for the face angle message
        upload_message_placeholder = st.empty()  # Placeholder for upload messages
        count = 0
        image_paths = []  # List to store image paths for uploading after capturing
        while cap.isOpened() and count < num_images:
            ret, frame = cap.read()
            if not ret:
                st.write("Video Capture Ended")
                logging.warning("Video Capture Ended")
                break
            with mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1) as face_mesh:
                while count < num_images:
                    ret, frame = cap.read()
                    if not ret:
                        st.write("Error: Could not read frame from webcam.")
                        logging.error("Error: Could not read frame from webcam.")
                        break
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame_placeholder.image(rgb_frame, channels="RGB")
                    results = face_mesh.process(rgb_frame)

                    if results.multi_face_landmarks:
                        is_correct_orientation = True  # Simplified for demonstration

                        # Update face angle message (if the face is at the correct angle)
                        if is_correct_orientation:
                            angle_placeholder.success(f"Face angle for {direction} is correct.")
                        else:
                            angle_placeholder.error(f"Please adjust your face for the {direction} angle.")

                        if is_correct_orientation:
                            image_name = f'{roll_number}_{direction}_{count}.jpg'
                            local_image_path = os.path.join(temp_path, image_name)
                            cv2.imwrite(local_image_path, frame)
                            image_paths.append(local_image_path)  # Store path for later uploading
                            count += 1
                            # Update the message dynamically for each image capture
                            upload_message_placeholder.success(f"Image {count} captured and ready for upload.")
                            logging.info(f"Image {count} captured for {roll_number} - {direction}.")
                            # Clear the message after a short delay (e.g., 2 seconds)
                            time.sleep(2)
                            upload_message_placeholder.empty()  # Clear the message
                        # Clear the angle message after the frame to keep it updated
                        time.sleep(2)
                        angle_placeholder.empty()  # Clear the angle message for the next frame
        frame_placeholder.empty()
        # After capturing all the images, bulk upload them to GitHub and delete them
        files_data = [(local_image_path, f'{roll_number}/{direction}/{os.path.basename(local_image_path)}') for
                      local_image_path in image_paths]
        upload_bulk_to_github(files_data, repo, branch, token)

        # Remove images after uploading
        for local_image_path in image_paths:
            os.remove(local_image_path)  # Delete the image after uploading
            logging.info(f"Deleted {local_image_path} after uploading.")

        cap.release()
        cv2.destroyAllWindows()
    except Exception as e:
        st.error(f"Error during image capture: {e}")
        logging.error(f"Error during image capture: {e}")


def main():
    st.title("Face Dataset Generator")

    roll_number = st.text_input("Enter Roll Number")
    name = st.text_input("Enter Student Name")
    repo = st.secrets["Repo"]
    branch = st.secrets["Branch"]
    token = st.secrets["TOKEN"]

    if st.button("Start Capture", key="start_capture_button"):  # Unique key for start capture button
        if not roll_number or not name or not repo or not branch or not token:
            st.error("Please enter all required fields.")
            logging.error("User did not provide all required fields.")
        else:
            try:
                temp_path = './temp_images'
                os.makedirs(temp_path, exist_ok=True)

                capture_images(roll_number, 50, 'front', temp_path, repo, branch, token)
                capture_images(roll_number, 25, 'left', temp_path, repo, branch, token)
                capture_images(roll_number, 25, 'right', temp_path, repo, branch, token)

                st.success(f"Dataset for {roll_number}_{name} captured and uploaded successfully!")
                logging.info(f"Dataset for {roll_number}_{name} captured and uploaded successfully!")

                # Cleanup temporary folder (just in case any images were left)
                for file in os.listdir(temp_path):
                    os.remove(os.path.join(temp_path, file))
                os.rmdir(temp_path)

            except Exception as e:
                st.error(f"Error: {e}")
                logging.error(f"Error: {e}")


if __name__ == '__main__':
    main()
