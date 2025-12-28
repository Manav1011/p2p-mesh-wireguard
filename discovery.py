import stun
import socket

def get_public_info():
    # Attempt to use a common Google STUN server
    print("Requesting details from STUN server...")
    try:
        nat_type, external_ip, external_port = stun.get_ip_info(
            stun_host='stun.l.google.com', 
            stun_port=19302
        )
        
        print("\n--- Network Info ---")
        print(f"NAT Type:     {nat_type}")
        print(f"External IP:   {external_ip}")
        print(f"External Port: {external_port}")
        print("--------------------")
        
        return external_ip, external_port
    except Exception as e:
        print(f"Error: {e}")
        return None, None

if __name__ == "__main__":
    get_public_info()
