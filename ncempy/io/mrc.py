'''
A module to read MRC files in python and numpy.
Written according to MRC specification at http://bio3d.colorado.edu/imod/betaDoc/mrc_format.txt
ALso works with FEI MRC files which include a special header block with experimental information.
written by: Peter Ercius, percius@lbl.gov
'''

import numpy as np

class fileMRC:
    
    def __init__(self, filename, verbose = False):
        '''
        Init opening the file and reading in the header.
        Read in the data in MRC format and other useful information.
        Output is a dictionary with the following values:

        Returns a dictionary with
          stack, voxelSize, filename, axisOrientations, {FEIinfo}
        Args:
            filename: string pointing to the filesystem location of the file.
            verbose: if True, debug information is printed.
        '''
        # check for string
        if not isinstance(filename, str):
            raise TypeError('Filename is supposed to be a string')
            
        self.filename = filename

        # necessary declarations, if something fails
        self.fid = None
#        self.fidOut = None
        
        self.dataOut = {} #will hold the data and metadata to output to the user after getDataset() call
        
        #Add a top level variable to indicate verbosee output for debugging
        self.v = verbose
        
        #Open the file and quit if the file does not exist
        try:
            self.fid = open(self.filename,'rb')
        except IOError as e:
            print("I/O error({0}): {1}".format(e.errno, e.strerror))
        
        #Store the original filename
        self.dataOut['filename'] = self.filename
        
        return None
    
    def __del__(self):
        #close the file
        if(not self.fid):
            if self.v:
                print('Closing input file: {}'.format(self.filename))
            self.fid.close()
#        if(self.fidOut):
#            if self.v:
#                print('Closing tags output file')
#            self.fidOut.close()
        return None
    
    def parseHeader(self):
        '''
        Read the header information which includes data type, data size, data
        shape, and metadata
        
        - Note: This header uses Fortran-style ordering. Numpy uses C-style ordering. The header is read in and then reversed [::-1] at the end for output to the user
        '''
        #Read in the initial header values
        head1 = np.fromfile(self.fid,dtype=np.int32,count=10)
        if self.v:
            print('header1 = {}'.format(head1))
        #Set the number of pixels for each dimension
        self.dataSize = head1[0:3]
        if self.v:
            print('dataSize (fortran ordering) = {}'.format(self.dataSize))
        
        #Set the data type and convert to numpy type
        self.mrcType = head1[3]
        self.dataType = self._getMRCType(self.mrcType)
        if self.v:
            print('dataType = {}'.format(self.dataType))
        
        #Get the grid size
        self.gridSize = head1[7:10]
        if self.v:
            print('mrc defined gridSize = {}'.format(self.gridSize))
            
        #Get the physical volume size (always in Angstroms) (starting at byte #11 in the file).
        head2 = np.fromfile(self.fid,dtype=np.float32,count=6)
        
        self.volumeSize = head2[0:3]
        if self.v:
            print('mrc defined volumeSize = {}'.format(self.volumeSize))
        
        #calculate the voxel size based on volume and grid sizes
        if self.volumeSize.any() ==0 or self.gridSize.any() ==0:
            if self.v:
                print('Detected 0 volume or grid size. Setting voxel size to 1 (Ang).')
            self.voxelSize = np.ones(3) #use 1 as a voxel size if its not set in the file
        else:
            self.voxelSize = (self.volumeSize / np.float32(self.gridSize))
            if self.v:
                print('voxelSize (Ang) = {}'.format(self.voxelSize))

        #Pixel (cell) angles
        self.cellAngles = head2[3:6]
        if self.v:
            print('cellAngles = {}'.format(self.cellAngles))
            
        #Axis orientations. Tells which axes are X,Y,Z
        self.axisOrientations = np.fromfile(self.fid,dtype=np.int32,count=3)
        if self.v:
            print('axisOrientations = {}'.format(self.axisOrientations))
        
        self.Shape = [self.dataSize[x-1] for x in self.axisOrientations]
        if self.v:
            print('data shape = {}'.format(self.Shape))
        
        #Min, max,mean
        self.minMaxMean = np.fromfile(self.fid,dtype=np.int32,count=3)
        
        #Extra information (for FEI MRC file, extra(1) is the size of the FEI information encoded with the file in terms of 4 byte floats)
        self.extra = np.fromfile(self.fid,dtype=np.int32,count=34)
        
        #Numpy uses C-style ordering. The header is written in Fortran-Style ordering. Flip the order of everything useful
        if self.v:
            print('Note: The MRC header is written in Fortran-Style ordering, but Numpy uses C-style ordering. This program will now reverse the order (using [::-1]) of useful metadata: (dataSize, gridSize,volumeSize,voxelSize,cellAngles,axisOrientations)')
        self.dataSize = self.dataSize[::-1]
        self.gridSize = self.gridSize[::-1]
        self.volumeSize = self.volumeSize[::-1]
        self.voxelSize = self.voxelSize[::-1]
        self.cellAngles = self.cellAngles[::-1]
        self.axisOrientations = self.axisOrientations[::-1]
        self.Shape = self.Shape[::-1]
        
        #Move to the end of the normal header
        self.fid.seek(1024)
        
        #Read in the extended header if it exists (for FEI MRC files)
        if self.extra[1] != 0:
            pos1 = self.fid.tell()
            if self.v:
                print('Extra header found. Most likely and FEI-style MRC file.')
                print('Position before reading extra header: ' + str(pos1))
                print('Extra header size = ' +str(self.extra[1]))
            
            '''
            Read the extra FEI header described as follows:
             1 a_tilt  first Alpha tilt (deg)
             2 b_tilt  first Beta tilt (deg)
             3 x_stage  Stage x position (Unit=m. But if value>1, unit=???m)
             4 y_stage  Stage y position (Unit=m. But if value>1, unit=???m)
             5 z_stage  Stage z position (Unit=m. But if value>1, unit=???m)
             6 x_shift  Image shift x (Unit=m. But if value>1, unit=???m)
             7 y_shift  Image shift y (Unit=m. But if value>1, unit=???m)
             8 defocus  starting Defocus Unit=m. But if value>1, unit=???m)
             9 exp_time Exposure time (s)
             10 mean_int Mean value of image
             11 tilt_axis   Tilt axis (deg)
             12 pixel_size  Pixel size of image (m)
             13 magnification   Magnification used
             14 voltage accelerating voltage
             15 ??
            '''
            FEIinfoValues = np.fromfile(self.fid,dtype=np.float32,count=15)
            FEIinfo = {'a_tilt':FEIinfoValues[0],'b_tilt':FEIinfoValues[1],'x_stage':FEIinfoValues[2],'y_stage':FEIinfoValues[3],'z_stage':FEIinfoValues[4],'x_shift':FEIinfoValues[5],'y_shift':FEIinfoValues[6],'defocus':FEIinfoValues[7],'exposure_time':FEIinfoValues[8],'mean':FEIinfoValues[9],'tilt_axis':FEIinfoValues[10],'pixel_size':FEIinfoValues[11],'magnification':FEIinfoValues[12],'voltage':FEIinfoValues[13],'unknown':FEIinfoValues[14]}
            
            self.voxelSize[0] = 1. #set this to 1 but it should be the tilt angles. These can be non-uniform though.
            self.voxelSize[1] = FEIinfo['pixel_size']*1e10 #convert [m] to Angstroms as is the standard for MRCs
            self.voxelSize[2] = FEIinfo['pixel_size']*1e10
        
        self.dataOffset = 1024+self.extra[1] #offset of the data from the start of the file
        
        #Add relevant information (metadata) to the output dictionary
        self.dataOut = {'voxelSize':self.voxelSize,'axisOrientations':self.axisOrientations,'cellAngles':self.cellAngles,'axisOrientations':self.axisOrientations}
        if self.extra[1] != 0:
            self.dataOut['FEIinfo'] = FEIinfo
        
        return 1
    
    def getDataset(self):
        '''Read in the full data block and reshape to a matrix
        with C-style ordering.
        
        '''
        self.fid.seek(self.dataOffset,0) #move to the start of the data from the start of the file
        try:
            data1 = np.fromfile(self.fid,dtype=self.dataType,count=np.prod(self.dataSize))#the dataSize needs to be reordered for numpy (c-style ordering). The fastest changing subscript is the last subscript.
            self.dataOut['data'] = data1.reshape(self.Shape)
        except MemoryError:
            print("Not enough memory to read in the full data set")        
        return self.dataOut
    
    def _applyAxisOrientations(self,arrayIn):
        ''' This is untested and unused.
        
        '''
        return [arrayIn[x-1] for x in self.axisOrientations]
    
    def _getMRCType(self, dataType):
        """Return the correct data type according to the official MRC type list:
        
         0 image : signed 8-bit bytes range -128 to 127
         1 image : 16-bit halfwords
         2 image : 32-bit reals
         3 transform : complex 16-bit integers
         4 transform : complex 32-bit reals
         6 image : unsigned 16-bit range 0 to 65535
        """
        if dataType == 0:
            Type = np.int8
        elif dataType == 1:
            Type = np.int16
        elif dataType == 2:
            Type = np.float32
        elif dataType ==  6:
            Type = np.uint16
        else:
            print("Unsupported data type" + str(dataType)) #complex data types are currently unsupported
        return Type
#end class fileMRC

def mrc2raw(fname):
    """Writes the image data in an MRC file as binary file with the same file
    name and .raw ending. Data type and size are written in the file name.
    No other header information is retained.
    
    """
    tomo = mrcReader(fname)
    #stackSize = tomo['stack'].shape
    #stackType = tomo['stack'].dtype
    rawName = tomo['filename'].rsplit('.',1)[0] + '_' + str(tomo['stack'].dtype) + '_' + str(tomo['stack'].shape) + '.raw'
    fid = open(rawName,'wb')
    fid.write(tomo['stack']) #write out as C ordered data
    fid.close()
    
#Convert an MRC data set to an EMD data set (HDF5 file type)
def mrc2emd(fname):
    """
    mrc2emd(fname)
    Writes the MRC file as an HDF5 file in EMD format with same file name and .emd ending. Header information is retained as attributes. See also emdXMF() to write out an XMF file for Tomviz.
    """
    import h5py
    
    #Read in the MRC data and reshape to C-style ordering
    tomo = mrcReader(fname)
    
    #create the HDF5 file
    try:
        f1 = h5py.File(fname.rsplit('.mrc',1)[0] + '.emd','w') #w- will error if the file exists
    except:
        print("Problem opening file. Maybe it already exists?")
        f1.close()
        del tomo
        return 0

    #Create the axis vectors in nanometers. Standard MRC pixel size is in Angstroms
    xFull = np.linspace(0,tomo['voxelSize'][0]*tomo['stack'].shape[0]-1,tomo['stack'].shape[0]) 
    yFull = np.linspace(0,tomo['voxelSize'][1]*tomo['stack'].shape[1]-1,tomo['stack'].shape[1])
    zFull = np.linspace(0,tomo['voxelSize'][2]*tomo['stack'].shape[2]-1,tomo['stack'].shape[2])
    
    #Root data group
    dataTop = f1.create_group('data')

    #Create tilt series group
    tiltseriesGroup = dataTop.create_group('stack')
    tiltseriesGroup.attrs['emd_group_type'] = np.int8(1)
    
    #Save the data to the EMD file and reshape it to a C-style array
    #tiltDset = tiltseriesGroup.create_dataset('data',data=tomo['stack'][1:100,1:100,1:100],compression='gzip',shuffle=True)
    try:
        tiltDset = tiltseriesGroup.create_dataset('data',data=tomo['stack'],compression='gzip',shuffle=True)
    except MemoryError:
        print("Not enough memory to write out data to EMD file")
        del tomo
        f1.close()
        return 0
        
    dim1 = tiltseriesGroup.create_dataset('dim1',data=xFull)
    dim1.attrs['name'] = np.string_('x')
    dim1.attrs['units'] = np.string_('')
    dim2 = tiltseriesGroup.create_dataset('dim2',data=yFull)
    dim2.attrs['name'] = np.string_('y')
    dim2.attrs['units'] = np.string_('')
    dim3 = tiltseriesGroup.create_dataset('dim3',data=zFull)
    dim3.attrs['name'] = np.string_('z')
    dim3.attrs['units'] = np.string_('')
    
    #Create the other groups
    scopeGroup = f1.create_group('Microscope')
    scopeGroup.attrs['voxel sizes'] = tomo['voxelSize']
    userGroup = f1.create_group('User')
    commentGroup = f1.create_group('Comments')
    
    #Possible way using keyword arguments to populate these fields
    #def greet_me(**kwargs):
    #if kwargs is not None:
    #    for key, value in kwargs.iteritems():
    #        print("%s == %s" %(key,value))
    
    f1.close()
    
    return 1
    
    
    
    
    
def mrcReader(fname,verbose=False):
    '''
    A simple function to read open a MRC, parse the header, and read the data
    '''
    f1 = fileMRC(fname,verbose) #open the file and init the class
    f1.parseHeader() #parse the header
    im1 = f1.getDataset() #read in the dataset
    del f1 #delete the class and close the file
    return im1 #return the data and metadata as a dictionary
    
def mrcWriter(filename,stack,pixelSize,forceWrite=False):
    """
    mrcWriter(filename,stack)
    Write out a MRC type file according to the specification at http://bio3d.colorado.edu/imod/doc/mrc_format.txt
      input:
        filename - The name of the EMD file 
        stack - The binary data to write to disk
        pixelSize - The size of the pixel along each direction (in Angstroms) as a 3 element vector (sizeX,sizeY,sizeZ). sizeZ could be the angular step for a tilt series
      output:
        Returns 1 if successful and 0 if unsuccessful
    """
    
    fid = open(filename,'wb')
    
    if len(stack.shape) > 3:
        print("Too many dimensions")
        return 0;
    
    if not stack.flags['C_CONTIGUOUS']:
        print("Error: Array must be C-style ordering: [numImages,Y,X]. Use numpy.tranpspose and np.ascontiguousarray to change data ordering in memory")
        print('Exiting')
        return 0;
    
    #initialize the header with 256 zeros with size 4 bytes
    header = np.zeros(256,dtype=np.int32)
    fid.write(header)
    fid.seek(0,0) #return to the beginning of the file
    
    #Initialize the int32 part of the header
    header1 = np.zeros(10,dtype=np.int32)
    
    #Write the number of columns, rows and sections (images)
    #header1[0:3] = np.int32(dims) #stack size in pixels
    header1[0] = np.int32(stack.shape[2]) #num columns, the last index in C-style ordering
    header1[1] = np.int32(stack.shape[1]) #num rows
    header1[2] = np.int32(stack.shape[0]) #num sections (images)
    
    if stack.dtype == np.float32:
        header1[3] = np.int32(2)
    elif stack.dtype == np.uint16:
        header1[3] = np.int32(6)
    elif stack.dtype == np.int16:
        header1[3] = np.int32(1)
    elif stack.dtype == np.int8:
        header1[3] = np.int32(0)
    else:
        print("Data type " + str(stack.dtype) + " is unsupported. Only int8, int16, uint16, and float32 are supported")
        return 0;
    
    #Starting point of sub image (not used in IMOD) 
    header1[4:7] = np.zeros(3,dtype=np.int32)
    
    #Grid size in X,Y,Z
    #header1[7:10] = np.int32(dims); #stack size in pixels
    header1[7] = np.int32(stack.shape[2]) #mx
    header1[8] = np.int32(stack.shape[1]) #my
    header1[9] = np.int32(stack.shape[0]) #mz
    
    #Write out the first part of the header information
    fid.write(header1)
    
    #Cell dimensions (in Angstroms)
    #pixel spacing = xlen/mx, ylen/my, zlen/mz
    fid.write(np.float32(pixelSize[2]*stack.shape[2])) #xlen
    fid.write(np.float32(pixelSize[1]*stack.shape[1])) #ylen
    fid.write(np.float32(pixelSize[0]*stack.shape[0])) #zlen
    
    #Cell angles (in degrees)
    fid.write(np.float32([90.0,90.0,90.0]))
    
    #Description of array directions with respect to: Columns, Rows, Images
    fid.write(np.int32([1,2,3]))
    
    #Minimum and maximum density
    np.int32(stack)
    fid.write(np.float32(np.min(stack)))
    fid.write(np.float32(np.max(stack)))
    fid.write(np.float32(np.mean(stack)))
    
    #Needed to indicate that the data is little endian for NEW-STYLE MRC image2000 HEADER - IMOD 2.6.20 and above
    fid.seek(212,0);
    fid.write(np.int8([68,65,0,0])) #use [17,17,0,0] for big endian
    
    #Write out the data
    fid.seek(1024);
    if forceWrite:    
        fid.write(np.ascontiguousarray(stack)); #Change to C ordering array for writing to disk
    else:
        fid.write(stack); #msut be C-contiguous

    #Close the file
    fid.close();
    return 1;
    
def emd2mrc(filename,dsetPath):
    """
    Convert EMD data set into MRC data set
    The final data type is float32 for convenience
      inputs:
        filename - The name of the EMD file
        dsetPath - the HDF5 path to the top group holding the data ex. '/data/raw/'
    """
    
    with h5py.File(filename,'r') as f1:
        #Get the pixel sizes and convert to Ang
        dimsPath = dsetPath + '/dim'
        print('Warning: Assuming EMD dim vectors are in nanometer')
        print('dim vector names/units are:')
        for ii in range(1,4):
            print('name, units = {}, {}'.format(f1[dimsPath+str(ii)].attrs['name'],f1[dimsPath+str(ii)].attrs['units']))
        pixelSizeX = (f1[dsetPath + '/dim2'][1] - f1[dsetPath + '/dim2'][0])*10 #change nanometers to Ang
        pixelSizeY = (f1[dsetPath + '/dim3'][1] - f1[dsetPath + '/dim3'][0])*10 #change nanometers to Ang
                
        filenameOut = filename.split('.emd')[0] + '.mrc' #use the first part of the file as the prefix removing the .emd on the end
        
        print('Warning: Converting to float32 before writing to disk')
        mrc.mrcWriter(filenameOut,np.float32(f1[dsetPath+'/data']),(1,pixelSizeY,pixelSizeX)) #the extra slash is not a problem. // is the same as / in a HDF5 data set path
        
        print('Finished writing to: {}'.format(filenameOut))
        
def h5XMF(filename,dataSetName):
    """
    h5XMF(fname,dataSetName)
    Write out an XMF file for an existing h5 file. XMF is a companion file to tell
    other programs the structure of an HDF5 file.
      input:
        filename - The name of the h5 file 
        dataSetName - The full path and name of the data set that holds the dataset
    """
    import h5py
    with h5py.File(filename,'r') as f1:
        #Get the shape of the data
        dataShape = f1[dataSetName].shape
        #Check to get datatype string and number of bytes
        if f1[dataSetName].dtype == np.dtype('float32'):
            dataTypeString = 'Float'
            precision = 4
        elif f1[dataSetName].dtype == np.dtype('float64'):
            dataTypeString = 'Float'
            precision = 8
        elif f1[dataSetName].dtype == np.dtype('int32'):
            dataTypeString = 'Int'
            precision = 4
        elif f1[dataSetName].dtype == np.dtype('uint32'):
            dataTypeString = 'UInt'
            precision = 4
        elif f1[dataSetName].dtype == np.dtype('int16'):
            dataTypeString = 'Short'
            precision = 2
        elif f1[dataSetName].dtype == np.dtype('uint16'):
            dataTypeString = 'UShort'
            precision = 2
        elif f1[dataSetName].dtype == np.dtype('int8'):
            dataTypeString = 'Char'
            precision = 1
        elif f1[dataSetName].dtype == np.dtype('int8'):
            dataTypeString = 'UChar'
            precision = 1
        else:
            print('Unknown datatype: {}'.format(f1[dataSetName].dtype))
            return 0
            #raise IOError('Error')
    
    #Get the pixel sizes for all 3 dimensions
    pixelSizes = [1,1,1] #use simple pixel size
    
    #Write an XMF with the data set path, name and size
    with open(filename + '.xmf','w') as f2:
        f2.write('<?xml version="1.0" ?>\n<!DOCTYPE Xdmf SYSTEM "Xdmf.dtd" []>\n<Xdmf xmlns:xi="http://www.w3.org/2003/XInclude" Version="2.2">\n<Domain>\n')
        f2.write('<Grid Name="' + filename + '" GridType="Uniform">\n')
        f2.write('<Topology TopologyType="3DCORECTMesh" Dimensions="' + str(dataShape[0]) + ' ' + str(dataShape[1]) + ' ' + str(dataShape[2]) + '"/>\n')
        f2.write('<Geometry GeometryType="ORIGIN_DXDYDZ">\n')
        f2.write('<DataItem Name="Origin" Dimensions="3" NumberType="Float" Precision="4" Format="XML">0 0 0</DataItem>\n')
        f2.write('<DataItem Name="Spacing" Dimensions="3" NumberType="Float" Precision="4" Format="XML">' + str(pixelSizes[0]) + ' ' + str(pixelSizes[1]) + ' ' + str(pixelSizes[2]) + '</DataItem>\n</Geometry>\n')
        f2.write('<Attribute Name="' + dataSetName + '" AttributeType="Scalar" Center="Node">\n')
        f2.write('<DataItem Format="HDF" NumberType="'+dataTypeString+'" Precision="'+ str(precision) + '" Dimensions="' + str(dataShape[0]) + ' ' + str(dataShape[1]) + ' ' + str(dataShape[2]) + '">' + filename + ':' + dataSetName + '</DataItem>\n')
        f2.write('</Attribute>\n</Grid>\n</Domain>\n</Xdmf>\n')
    
    return 1
    
def emdXMF(filename,dataSetName):
    """
    emdXMF(fname,dataSetName)
    Write out an XMF file which tells programs the structure of the HDF5 file.
      input:
        filename - The name of the EMD file 
        dataSetName - The name of the data group that holds the dataset in the EMD top level data folder. Not the full path to the dataset.
    """
    import h5py
    with h5py.File(filename,'r') as f1:
        #Get the shape of the data
        dataShape = f1['data'][dataSetName]['data'].shape
        #Get the pixel sizes for all 3 dimensions
        pixelSizes = (f1['data'][dataSetName]['dim1'][1] - f1['data'][dataSetName]['dim1'][0], f1['data'][dataSetName]['dim2'][1] - f1['data'][dataSetName]['dim2'][0], f1['data'][dataSetName]['dim3'][1] - f1['data'][dataSetName]['dim3'][0])
        
        #Determine the data type and number of bytes
        if f1['data'][dataSetName]['data'].dtype == np.dtype('float32'):
            dataTypeString = 'Float'
            precision = 4
        elif f1['data'][dataSetName]['data'].dtype == np.dtype('float64'):
            dataTypeString = 'Float'
            precision = 8
        elif f1['data'][dataSetName]['data'].dtype == np.dtype('int32'):
            dataTypeString = 'Int'
            precision = 4
        elif f1['data'][dataSetName]['data'].dtype == np.dtype('uint32'):
            dataTypeString = 'UInt'
            precision = 4
        elif f1['data'][dataSetName]['data'].dtype == np.dtype('int16'):
            dataTypeString = 'Short'
            precision = 2
        elif f1['data'][dataSetName]['data'].dtype == np.dtype('uint16'):
            dataTypeString = 'UShort'
            precision = 2
        elif f1['data'][dataSetName]['data'].dtype == np.dtype('int8'):
            dataTypeString = 'Char'
            precision = 1
        elif f1['data'][dataSetName]['data'].dtype == np.dtype('int8'):
            dataTypeString = 'UChar'
            precision = 1
        else:
            print('Unknown datatype: {}'.format(f1[dataSetName].dtype))
            return 0
    
    #Write an XMF with the data set path, name and size
    with open(filename.strip('emd') + 'xmf','w') as f2:
        f2.write('<?xml version="1.0" ?>\n<!DOCTYPE Xdmf SYSTEM "Xdmf.dtd" []>\n<Xdmf xmlns:xi="http://www.w3.org/2003/XInclude" Version="2.2">\n<Domain>\n')
        f2.write('<Grid Name="' + filename.strip('.emd') + '" GridType="Uniform">\n')
        f2.write('<Topology TopologyType="3DCORECTMesh" Dimensions="' + str(dataShape[0]) + ' ' + str(dataShape[1]) + ' ' + str(dataShape[2]) + '"/>\n')
        f2.write('<Geometry GeometryType="ORIGIN_DXDYDZ">\n')
        f2.write('<DataItem Name="Origin" Dimensions="3" NumberType="Float" Precision="4" Format="XML">0 0 0</DataItem>\n')
        f2.write('<DataItem Name="Spacing" Dimensions="3" NumberType="Float" Precision="4" Format="XML">' + str(pixelSizes[0]) + ' ' + str(pixelSizes[1]) + ' ' + str(pixelSizes[2]) + '</DataItem>\n</Geometry>\n')
        f2.write('<Attribute Name="' + dataSetName + '" AttributeType="Scalar" Center="Node">\n')
        f2.write('<DataItem Format="HDF" NumberType="'+dataTypeString+'" Precision="'+ str(precision) + '" Dimensions="' + str(dataShape[0]) + ' ' + str(dataShape[1]) + ' ' + str(dataShape[2]) + '">' + filename + ':/data/' + dataSetName+ '/data</DataItem>\n')
        f2.write('</Attribute>\n</Grid>\n</Domain>\n</Xdmf>\n')
        #f2.close()
    
    return 1