import jarray
import inspect
import os
import subprocess

from java.lang import System
from java.util.logging import Level
from org.sleuthkit.datamodel import SleuthkitCase
from org.sleuthkit.datamodel import AbstractFile
from org.sleuthkit.datamodel import Score
from org.sleuthkit.datamodel import ReadContentInputStream
from org.sleuthkit.datamodel import BlackboardArtifact
from org.sleuthkit.datamodel import BlackboardAttribute
from org.sleuthkit.autopsy.ingest import IngestModule
from org.sleuthkit.autopsy.ingest.IngestModule import IngestModuleException
from org.sleuthkit.autopsy.ingest import DataSourceIngestModule
from org.sleuthkit.autopsy.ingest import FileIngestModule
from org.sleuthkit.autopsy.ingest import IngestModuleFactoryAdapter
from org.sleuthkit.autopsy.ingest import IngestMessage
from org.sleuthkit.autopsy.ingest import IngestServices
from org.sleuthkit.autopsy.coreutils import Logger
from org.sleuthkit.autopsy.casemodule import Case
from org.sleuthkit.autopsy.casemodule.services import Services
from org.sleuthkit.autopsy.casemodule.services import FileManager
from org.sleuthkit.autopsy.casemodule.services import Blackboard
from org.sleuthkit.datamodel import Score
from java.util import Arrays
from org.sleuthkit.autopsy.datamodel import ContentUtils
from java.io import File
from org.sleuthkit.datamodel.BlackboardAttribute import Type
from org.sleuthkit.autopsy.ingest import ModuleDataEvent

# Factory that defines the name and details of the module and allows Autopsy
# to create instances of the modules that will do the analysis.
class WeaponsMoneyDetectorDataSourceIngestModuleFactory(IngestModuleFactoryAdapter):

    moduleName = "Weapons and Money Detector"

    def getModuleDisplayName(self):
        return self.moduleName

    def getModuleDescription(self):
        return "Module that detects pistols, bills, knives and credit cards in images."

    def getModuleVersionNumber(self):
        return "1.0"

    def isDataSourceIngestModuleFactory(self):
        return True

    def createDataSourceIngestModule(self, ingestOptions):
        return WeaponsMoneyDetectorDataSourceIngestModule()


# Data Source-level ingest module.  One gets created per data source.
class WeaponsMoneyDetectorDataSourceIngestModule(DataSourceIngestModule):
    _logger = Logger.getLogger(WeaponsMoneyDetectorDataSourceIngestModuleFactory.moduleName)
    
    _supported_image_types = [
        'image/jpeg',  # JPG, JPEG
        'image/png',   # PNG
        'image/gif',   # GIF
        'image/bmp',   # BMP
        'image/tiff',  # TIFF
        'image/webp'   # WEBP
    ]

    def log(self, level, msg):
        self._logger.logp(level, self.__class__.__name__, inspect.stack()[1][3], msg)

    def __init__(self):
        self.context = None

    # Where any setup and configuration is done
    # 'context' is an instance of org.sleuthkit.autopsy.ingest.IngestJobContext.
    # See: http://sleuthkit.org/autopsy/docs/api-docs/latest/classorg_1_1sleuthkit_1_1autopsy_1_1ingest_1_1_ingest_job_context.html
    def startUp(self, context):
        
        # Checking for necessary files
        module_path = os.path.dirname(os.path.abspath(__file__))
        utils_path = os.path.join(module_path, 'utils')
        path_to_model = os.path.join(utils_path, 'model')
        path_to_exe = os.path.join(utils_path, 'dist')
        
        self.exe_path = os.path.join(path_to_exe, 'weaponsMoneyDetector.exe')
        if not os.path.exists(self.exe_path):
            raise IngestModuleException('Executable file not found!')

        self.model_path = os.path.join(path_to_model, 'best.pt')
        if not os.path.exists(self.model_path):
            raise IngestModuleException('YoloV8 model is not found!')
        
        
        self.context = context

    # Where the analysis is done.
    # The 'dataSource' object being passed in is of type org.sleuthkit.datamodel.Content.
    # See: http://www.sleuthkit.org/sleuthkit/docs/jni-docs/latest/interfaceorg_1_1sleuthkit_1_1datamodel_1_1_content.html
    # 'progressBar' is of type org.sleuthkit.autopsy.ingest.DataSourceIngestModuleProgress
    # See: http://sleuthkit.org/autopsy/docs/api-docs/latest/classorg_1_1sleuthkit_1_1autopsy_1_1ingest_1_1_data_source_ingest_module_progress.html
    def process(self, dataSource, progressBar):

        # we don't know how much work there is yet
        progressBar.switchToIndeterminate()

        # get files with supported MIME Type
        try:            
            fileManager = Case.getCurrentCase().getServices().getFileManager()
            files = fileManager.findFilesByMimeType(dataSource, self._supported_image_types)
        except TskCoreException:
            self.log(Level.SEVERE, 'Error getting files')
            return IngestModule.ProcessResult.ERROR
            
        # count the files
        num_files = len(files)
        if not num_files:
            message = "No images found: did you run the 'File Type Identification' module before running 'Weapons and Money Detector'?"
            self.log(Level.WARNING, message)
            self.notifyUser(IngestMessage.MessageType.WARNING, message)
            return IngestModule.ProcessResult.OK
            
        self.log(Level.INFO, 'Found ' + str(num_files) + ' files')

        # amount of work: copy each file + process each file
        progressBar.switchToDeterminate(num_files * 2)
        

        # create temp directory, if not exists
        self.temp_dir = self.createTempDir(dataSource.getName())
        self.log(Level.INFO, 'Temp dir:' + self.temp_dir)
        
        # set results directory
        self.results_dir = os.path.join(Case.getCurrentCase().getModulesOutputDirAbsPath(), 
            WeaponsMoneyDetectorDataSourceIngestModuleFactory.moduleName, dataSource.getName(), 'results')
        self.log(Level.INFO, 'Results dir:' + self.results_dir)
            
        ##### Copy the files to the temp directory     
        file_counter = 0
        for file in files:
            # Check if the user pressed cancel while we were busy
            if self.context.isJobCancelled():
                return IngestModule.ProcessResult.OK
            file_size = file.getSize()
            if file_size <= 0:
                self.log(Level.WARNING, 'File ' + file.getName() + ' seems corrupted (size not > 0)')
            else:
                # copy file
                ContentUtils.writeToFile(file, File(os.path.join(self.temp_dir, file.getName())))
                
            # Update the progress bar
            file_counter += 1
            progressBar.progress('copying files to temporary directory', file_counter)

        if self.context.isJobCancelled():
            return IngestModule.ProcessResult.OK
            
        # Call the external executable file
        process = subprocess.Popen(
            [self.exe_path, self.model_path, self.temp_dir, self.results_dir],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            self.notifyUser(IngestMessage.MessageType.ERROR, 'Error running detection: ' + stderr.decode("utf-8"))
            raise Exception("Error in YOLO script: " + stderr.decode("utf-8"))
        
        ##### Handle results
        results_file_path = os.path.join(self.results_dir, 'report.txt')
        
        results_count = 0
        
        artifacts = []
        
        with open(results_file_path, 'r') as file:
            lines = file.readlines()
            
        process_counter = 0
        for line in lines:
            if ', Tags: ' in line:
                    # Parse the line
                    image_name, tags = line.strip().split(', Tags: ')
                    tags_list = [] if tags == "No objects detected" else tags.split(', ')
                    
                    # Update the progress bar
                    process_counter += 1
                    progressBar.progress('processing files', num_files + process_counter)
                    
                    # Skip images without tags
                    if not tags_list:
                        continue
                    
                    results_count += 1
                    
                    for file in files:
                        if file.getName() == image_name:
                            self.postOnBlackboard(file, tags_list, artifacts)
                            
        
        ##### Post a success message to the ingest messages in box
        message = IngestMessage.createMessage(IngestMessage.MessageType.DATA,
            WeaponsMoneyDetectorDataSourceIngestModuleFactory.moduleName, 
            "Processed %d image files: found %d results." % (file_counter, results_count))
        IngestServices.getInstance().postMessage(message)

        return IngestModule.ProcessResult.OK
        
    def notifyUser(self, message_type, message):
        ingest_message = IngestMessage.createMessage(message_type,
            WeaponsMoneyDetectorDataSourceIngestModuleFactory.moduleName, message)
        IngestServices.getInstance().postMessage(ingest_message)
        
    def createTempDir(self, data_source_name):
        temp_dir = os.path.join(Case.getCurrentCase().getModulesOutputDirAbsPath(), 
            WeaponsMoneyDetectorDataSourceIngestModuleFactory.moduleName, data_source_name, 'original_files')
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        return temp_dir
        
    def postOnBlackboard(self, file, tags_list, artifacts):
        #Skip file with already detected objects
        file_artifacts = file.getArtifacts(BlackboardArtifact.ARTIFACT_TYPE.TSK_INTERESTING_FILE_HIT)
        for file_artifact in file_artifacts:
            set_name_attr = file_artifact.getAttribute(Type(BlackboardAttribute.ATTRIBUTE_TYPE.TSK_SET_NAME))
            if set_name_attr:
                set_name_value = set_name_attr.getValueString()
                if set_name_value == "Weapons and Money in Images":
                    return
                    
        
        art = file.newArtifact(BlackboardArtifact.ARTIFACT_TYPE.TSK_INTERESTING_FILE_HIT)

        att = BlackboardAttribute(BlackboardAttribute.ATTRIBUTE_TYPE.TSK_SET_NAME.getTypeID(),

          WeaponsMoneyDetectorDataSourceIngestModuleFactory.moduleName, "Weapons and Money in Images")

        art.addAttribute(att)
        
        att_comment = BlackboardAttribute(BlackboardAttribute.ATTRIBUTE_TYPE.TSK_COMMENT, 
            WeaponsMoneyDetectorDataSourceIngestModuleFactory.moduleName, u"Detected objects: %s" % ', '.join(tags_list))

        art.addAttribute(att_comment)

        artifacts.append(art)
        
        
        # Fire an event to notify the UI and others that there is a new artifact

        IngestServices.getInstance().fireModuleDataEvent(

            ModuleDataEvent(WeaponsMoneyDetectorDataSourceIngestModuleFactory.moduleName,

                BlackboardArtifact.ARTIFACT_TYPE.TSK_INTERESTING_FILE_HIT, artifacts));
                
        