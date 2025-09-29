import os

def main():
    # Prompt the user for the Docker image tag
    tag = input("Unesite tag za Docker image (npr. v0.0.1.rc7-dev): ").strip()
    
    # Default tag if none is provided
    if not tag:
        tag = "v0.0.1.rc3-dev"
    
    # Pokreni qemu-user-static kako bi omogućio ARM emulaciju
    print("Pokrećem qemu-user-static za ARM emulaciju...")
    os.system("docker run --rm --privileged multiarch/qemu-user-static --reset -p yes")

    # Define the build context and Dockerfile paths
    build_context = os.path.abspath("c:/Users/filip/OneDrive/Desktop/diplomski_rad/db_cont")
    dockerfile_path = os.path.join(build_context, "Dockerfile")
    
    # Define the Docker build command
    command = (
        f"docker buildx build --platform linux/arm64 "
        f"-t db_cont:{tag} "
        f"-f {dockerfile_path} {build_context} --load"
    )
    
    # Print the command for confirmation
    print(f"Pokrećem naredbu: {command}")
    
    # Execute the Docker build command
    os.system(command)

    # Export to .tar
    output_tar = f"db_cont_{tag}.tar"
    save_command = f"docker save db_cont:{tag} > {output_tar}"
    print(f"Exportam Docker image u {output_tar}...")
    os.system(save_command)

if __name__ == "__main__":
    main()