FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
   && apt-get install -y --no-install-recommends \
   build-essential \
   git \
   curl \
   ca-certificates \
   sudo \
   unzip \
   sshfs \
   iputils-ping \
   zsh \
   wget \
   vim \
   && apt-get autoremove -y \
   && apt-get clean -y \
   && rm -rf /var/lib/apt/lists/*


WORKDIR /tmp

# Copy explicit requirements files into the image so we can install during build
COPY supabase/ui/requirements.txt .

# pip install using a permanent cache to avoid downloads on every build
RUN --mount=type=cache,target=/root/.cache/pip \
   pip install --upgrade pip setuptools wheel \
   && pip install -r requirements.txt 


# Install Powerline fonts for zsh theme
RUN git clone https://github.com/powerline/fonts.git && \
   cd fonts && \
   ./install.sh && \
   cd .. && \
   rm -rf fonts

# Optional: Set Zsh as the default shell for a specific user
# This step is typically done if you want the container to launch into Zsh by default
# For example, to set Zsh for the 'root' user:
RUN chsh -s /usr/bin/zsh $USERNAME


WORKDIR /workspace
ARG USER_UID=1000
ARG USER_GID=1000

# Create the user
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
   && useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME \
   #
   # [Optional] Add sudo support. Omit if you don't need to install software after connecting.        
   && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
   && chmod 0440 /etc/sudoers.d/$USERNAME || true

# [Optional] Set the default user. Omit if you want to keep the default as root.
USER $USERNAME

RUN echo "Install ohmyzsh"

RUN sh -c "$(wget -O- https://github.com/deluan/zsh-in-docker/releases/download/v1.2.1/zsh-in-docker.sh)" -- \
   -t agnoster \
   -p git \
   -p https://github.com/zsh-users/zsh-autosuggestions \
   -p https://github.com/zsh-users/zsh-completions \
   -p https://github.com/zsh-users/zsh-history-substring-search \
   -p https://github.com/zsh-users/zsh-syntax-highlighting \
   -p 'history-substring-search' \
   -a 'bindkey "\$terminfo[kcuu1]" history-substring-search-up' \
   -a 'bindkey "\$terminfo[kcud1]" history-substring-search-down'

# Expose the port Streamlit runs on
EXPOSE 8501 

# Set the default command to run Zsh when the container starts
ENTRYPOINT [ "/bin/zsh" ]
CMD ["-l"]