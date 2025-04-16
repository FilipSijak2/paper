import os

def main():
    # Prompt the user for the Docker image tag
    tag = input("Unesite tag za Docker image (npr. v0.0.1.rc3-dev): ").strip()
    
    # Default tag if none is provided
    if not tag:
        tag = "v0.0.1.rc3-dev"
    
    # Define the build context and Dockerfile paths
    build_context = os.path.abspath("c:/Users/filip/OneDrive/Desktop/diplomski_rad/laser_driver_cont")
    dockerfile_path = os.path.join(build_context, "Dockerfile")
    
    # Define the Docker build command
    command = (
        f"docker buildx build --platform linux/arm64 "
        f"-t driver_cont:{tag} "
        f"-f {dockerfile_path} {build_context} --load"
    )
    
    # Print the command for confirmation
    print(f"Pokrećem naredbu: {command}")
    
    # Execute the Docker build command
    os.system(command)

if __name__ == "__main__":
    main()