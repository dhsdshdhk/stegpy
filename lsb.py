#!/usr/bin/env python3
# Module for processing images, audios and the least significant bits.

import numpy
from PIL import Image
from crypt import encrypt_info, decrypt_info

MAGIC_NUMBER = b'stegv3'

class HostElement:
    """ This class holds information about a host element. """
    def __init__(self, filename):
        self.filename = filename
        self.format = filename[-3:]
        self.header, self.data = get_file(filename)

    def save(self):
        if self.format.lower() == 'wav':
            sound = numpy.concatenate((self.header, self.data))
            sound.tofile('_' + self.filename)
        else:
            if not self.filename.lower().endswith(('png', 'bmp')):
                print("Host has a lossy format and will be converted to PNG.")
                image = Image.fromarray(self.data)
                image.save('_' + self.filename[:-3] + 'png')

    def insert_message(self, message, bits=2, parasite_filename=None, password=None):
        raw_message_len = len(message).to_bytes(4, 'big')
        formatted_message = format_message(message, raw_message_len, parasite_filename)
        if password:
            formatted_message = encrypt_info(password, formatted_message)
        self.data = encode_message(self.data, formatted_message, bits)

    def read_message(self, password=None):
        msg = decode_message(self.data)
        
        if password:
            try:
                salt = bytes(msg[:16])
                msg = decrypt_info(password, bytes(msg[16:]), salt)
            except:
                print("Wrong password.")
                return

        check_magic_number(msg)
        msg_len = int.from_bytes(bytes(msg[6:10]), 'big')
        filename_len = int.from_bytes(bytes(msg[10:11]), 'big')

        start = filename_len + 11
        end = start + msg_len
        end_filename = filename_len + 11
        if(filename_len > 0):
            filename = '_' + bytes(msg[11:end_filename]).decode('utf-8')
        
        else:
            text = bytes(msg[start:end]).decode('utf-8')
            print(text)
            return

        with open(filename, 'wb') as f:
            f.write(bytes(msg[start:end]))

        print('File {} succesfully extracted from {}'.format(filename, '_' + self.filename))

    def free_space(self, bits=2):
        shape = self.data.shape
        self.data.shape = -1
        free = self.data.size * bits // 8
        self.data.shape = shape
        self.free = free
        return free

def get_file(filename):
    ''' Returns a numpy array of a host file so that one can access values[x][y]. '''
    if filename.lower().endswith('wav'): # There's a problem with WAV files. Their header has variable length, some of them contain little information, others contain even the lyrics.
        # Maybe I should drop them, or use something to separate exactly their data and header.
        content = numpy.fromfile(filename, dtype=numpy.uint8)
        content = content[:200], content[200:]
    else:
        image = Image.open(filename)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        content = None, numpy.array(image)
    return content

def format_message(message, msg_len, filename=None):
    if not filename: # text
        message = MAGIC_NUMBER + msg_len + (0).to_bytes(1, 'big') + message
    else:
        filename = filename.encode('utf-8')
        filename_len = len(filename).to_bytes(1, 'big')
        message = MAGIC_NUMBER + msg_len + filename_len + filename + message
    return message;

def encode_message(host_data, message, bits):
    ''' Encodes the byte array in the image numpy array. '''
    shape = host_data.shape
    host_data.shape = -1, # convert to 1D
    uneven = 0
    divisor = 8 // bits

    print("Host dimension: {:,} bytes".format(host_data.size))
    print("Message size: {:,} bytes".format(len(message)))
    print("Maximum size: {:,} bytes".format(host_data.size // divisor))

    check_message_space(host_data.size // divisor, len(message))
 
    if(host_data.size % divisor != 0): # Hacky way to deal with pixel arrays that cannot be divided evenly
        uneven = 1
        original_size = host_data.size
        host_data = numpy.resize(host_data, host_data.size + (divisor - host_data.size % divisor))

    msg = numpy.zeros(len(host_data) // divisor, dtype=numpy.uint8)

    msg[:len(message)] = list(message)

    host_data[:divisor*len(message)] &= 256 - 2 ** bits # clear last bit(s)
    for i in range(divisor):
        host_data[i::divisor] |= msg >> bits*i & (2 ** bits - 1) # copy bits to host_data

    operand = (0 if (bits == 1) else (16 if (bits == 2) else 32))
    host_data[0] = (host_data[0] & 207) | operand # 5th and 6th bits = log_2(bits)

    if uneven:
        host_data = numpy.resize(host_data, original_size)
    
    host_data.shape = shape # restore the 3D shape
    
    return host_data

def check_message_space(max_message_len, message_len):
    ''' Checks if there's enough space to write the message. '''
    if(max_message_len < message_len):
        print('You have too few colors to store that message. Aborting.')
        exit(-1)
    else:
        print('Ok.')

def decode_message(host_data):
    ''' Decodes the image numpy array into a byte array. '''
    host_data.shape = -1, # convert to 1D
    bits = 2 ** ((host_data[0] & 48) >> 4) # bits = 2 ^ (5th and 6th bits)    
    divisor = 8 // bits

    if(host_data.size % divisor != 0):
        host_data = numpy.resize(host_data, host_data.size + (divisor - host_data.size % divisor))

    msg = numpy.zeros(len(host_data) // divisor, dtype=numpy.uint8)

    for i in range(divisor):
        msg |= (host_data[i::divisor] & (2 ** bits - 1)) << bits*i

    return msg

def check_magic_number(msg):
    if bytes(msg[0:6]) != MAGIC_NUMBER:
        print(bytes(msg[:6]))
        print('ERROR! No encoded info found!')
        exit(-1)

if __name__ == '__main__':
    with open('hue.7z', 'rb') as f:
        message = f.read()
    host = HostElement('high_res.jpg')
    print(host.free_space(4))
    host.insert_message(message, bits=4, parasite_filename='hue.7z')
    host.save()
    host2 = HostElement('_high_res.png')
    host2.read_message()
