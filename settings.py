import os

ANDROID_JAR_PATH = '{0}/Android/Sdk/platforms/android-19/android.jar'.format(os.environ['HOME'])

WORKING_DIR = os.getcwd()
LIBS_DIR = os.path.join(WORKING_DIR, 'libs')
INPUT_DIR = os.path.join(WORKING_DIR, 'data', 'input')
INSTRUMENTED_DIR = os.path.join(WORKING_DIR, 'data', 'instrumented')
TOOLS_DIR = os.path.join(WORKING_DIR, 'data', 'tools')
TRACE_DIR = os.path.join(WORKING_DIR, 'trace')
RESULTS_DIR = os.path.join(WORKING_DIR, 'results')

KEYSTORE_PATH = os.path.join(WORKING_DIR, 'data', 'keystores', 'droidfax.jks')
KEYSTORE_PASSWORD = '123456'
KEYALIAS = 'droidfax'

AVD_NAME = 'Nexus-One-10'
EXECUTION_TIMEOUT = 60