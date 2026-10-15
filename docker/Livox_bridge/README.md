Build the thing 
cd /something/someting/livox_bridge 
docker compose build bridge


set environment variables for the machines u know 
export ROS_IP=192.168.1.133  # Replace with your laptop’s address
export ROS_DOMAIN_ID=31

Start the bridge in the background, then open a shell inside it:
docker compose up -d bridge
docker compose exec -it bridge bash
