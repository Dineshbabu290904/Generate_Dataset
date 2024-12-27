import streamlit as st
import requests
import base64
import os
import logging

# Set up logging to log to a file and to the console
logging.basicConfig(filename='dataset_generator.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


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


def main():
    st.title("Face Dataset Generator")

    roll_number = st.text_input("Enter Roll Number")
    name = st.text_input("Enter Student Name")
    repo = st.secrets["Repo"]
    branch = st.secrets["Branch"]
    token = st.secrets["TOKEN"]

    st.markdown(
        """
        <h3>Camera Feed</h3>
        <p>Click "Capture Image" to capture and upload images from your device's camera.</p>
        <video id="video" width="640" height="480" autoplay></video>
        <button id="capture">Capture Image</button>
        <canvas id="canvas" width="640" height="480" style="display:none;"></canvas>
        <script>
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const captureButton = document.getElementById('capture');
        const constraints = { video: true };

        navigator.mediaDevices.getUserMedia(constraints)
            .then((stream) => {
                video.srcObject = stream;
            })
            .catch((err) => {
                console.error('Error accessing the camera: ', err);
            });

        captureButton.addEventListener('click', () => {
            const context = canvas.getContext('2d');
            context.drawImage(video, 0, 0, canvas.width, canvas.height);
            const dataURL = canvas.toDataURL('image/jpeg');
            fetch('/upload_image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: dataURL })
            }).then(response => response.json())
              .then(data => console.log(data))
              .catch(err => console.error(err));
        });
        </script>
        """,
        unsafe_allow_html=True
    )

    if "captured_images" not in st.session_state:
        st.session_state["captured_images"] = []

    if st.button("Start Upload"):
        if not roll_number or not name or not repo or not branch or not token:
            st.error("Please enter all required fields.")
            return

        try:
            temp_path = '/tmp/temp_images'
            os.makedirs(temp_path, exist_ok=True)

            # Assume captured images are stored in session state
            for idx, image_data in enumerate(st.session_state["captured_images"]):
                image_path = os.path.join(temp_path, f'{roll_number}_image_{idx}.jpg')
                with open(image_path, "wb") as img_file:
                    img_file.write(base64.b64decode(image_data.split(",")[1]))

            files_data = [(os.path.join(temp_path, f), f'{roll_number}/image_{idx}.jpg')
                          for idx, f in enumerate(os.listdir(temp_path))]
            upload_bulk_to_github(files_data, repo, branch, token)

            for file in os.listdir(temp_path):
                os.remove(os.path.join(temp_path, file))
            os.rmdir(temp_path)

            st.success(f"Dataset for {roll_number}_{name} uploaded successfully!")

        except Exception as e:
            st.error(f"Error: {e}")


if __name__ == '__main__':
    main()
