# CARP Streamlit App

## Running Locally

```bash
# clone repo
git clone git@github.com:davekokel/carp_v2_mirror.git
cd carp_v2_mirror

# install dependencies
conda create -n carp python=3.12
conda activate carp
pip install -r requirements.txt

# run app
streamlit run streamlit_app.py
