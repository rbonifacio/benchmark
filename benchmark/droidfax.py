import logging
import os
import time

from settings import INPUT_DIR, INSTRUMENTED_DIR, LIBS_DIR, ANDROID_JAR_PATH, KEYSTORE_PASSWORD, KEYSTORE_PATH, KEYALIAS, AVD_NAME, TRACE_DIR, EXECUTION_TIMEOUT, RESULTS_DIR, WORKING_DIR
from .commands.command import Command
import signal
import re
import shutil

class DroidFax:

    @classmethod
    def run(cls, *args):
        # Arg parse
        path = WORKING_DIR+args[0].path
        repetitions = args[0].r
        timeout = args[0].t
        tools = args[0].tools
        # End Arg parse

        cls.phase_one_instrumentation(path)
        cls.phase_two_execution(timeout, tools)
        # cls.phase_three_results()

    @staticmethod
    def phase_one_instrumentation(input_path):
        logging.info('Droidfax\'s Phase 1: Instrumentation')
        
        # Create a folder to store intrumented apps if it doesn't exist.
        try:
            if not os.path.exists(INSTRUMENTED_DIR):
                os.mkdir(INSTRUMENTED_DIR)
        except OSError:
            error_msg = 'Error while creating folder {0}'.format(INSTRUMENTED_DIR)
            logging.error(error_msg)
            raise Exception(error_msg)

        # Collect instrumentation dependencies
        libs = list(map(lambda dep: os.path.join(LIBS_DIR, dep), os.listdir(LIBS_DIR)))
        main_cp = ':'.join(libs)

        # Collect soot dependencies
        droidfax_jar = os.path.join(LIBS_DIR, 'droidfax.jar')
        soot_cp = "{0}:{1}".format(droidfax_jar, ANDROID_JAR_PATH)

        for file in os.listdir(input_path):

            # Verify if apk is already instrumented.
            if os.path.exists(os.path.join(INSTRUMENTED_DIR, file)):
                logging.info('Using instrumented {0}'.format(file))
                continue
            
            start = time.time()

            # Instrument app
            logging.info('Intrumenting {0}'.format(file))
            instrument_cmd = Command('java', [
                '-Xmx14g', 
                '-ea', 
                '-cp',
                main_cp,
                'dynCG.sceneInstr',
                '-w',
                '-cp',
                soot_cp,
                '-p',
                'cg',
                'verbose:false,implicit-entry:true',
                '-p',
                'cg.spark',
                'verbose:false,on-fly-cg:true,rta:false',
                '-d',
                os.path.join(INSTRUMENTED_DIR),
                '-instr3rdparty',
                '-process-dir',
                os.path.join(input_path, file)
            ], 1200)
            instrument_result = instrument_cmd.invoke()

            end = time.time()
            logging.info('Static analisys finished. Elapsed time: {0}'.format(end - start))

            # Signing instrumented app
            logging.info('Signing {0}'.format(file))
            sign_cmd = Command('jarsigner', [
                '-verbose', 
                '-sigalg', 
                'SHA1withRSA',
                '-digestalg',
                'SHA1',
                '-storepass',
                KEYSTORE_PASSWORD,
                '-keystore',
                KEYSTORE_PATH,
                os.path.join(INSTRUMENTED_DIR, file),
                KEYALIAS
            ])
            sign_result = sign_cmd.invoke()

            logging.info('Verify the signature just added')
            verify_cmd = Command('jarsigner', [
                '-verify',
                '-verbose',
                '-certs',
                os.path.join(INSTRUMENTED_DIR, file)
            ])
            verify_result = verify_cmd.invoke()

    @classmethod
    def phase_two_execution(cls, timeout, tools):
        logging.info('Droidfax\'s Phase 2: Execution')

        # Verification of the timeout time ratio according to the number of apks in the input folder
        apks_qnt = len(os.listdir(INSTRUMENTED_DIR))
        tools_qnt = len(tools)
        timeout_by_apk = (timeout/apks_qnt)/tools_qnt

        # Create a folder to store execution trace
        try:
            if not os.path.exists(TRACE_DIR):
                os.mkdir(TRACE_DIR)
                os.mkdir(os.path.join(TRACE_DIR, "droidbot"))
                os.mkdir(os.path.join(TRACE_DIR, "monkey"))
            else:
                # Delete previous traces
                for file in os.listdir(os.path.join(TRACE_DIR, "droidbot")):
                    os.remove(os.path.join(TRACE_DIR, "droidbot", file))
                for file in os.listdir(os.path.join(TRACE_DIR, "monkey")):
                    os.remove(os.path.join(TRACE_DIR, "monkey", file))
        except OSError:
            error_msg = 'Error while creating folder {0}'.format(TRACE_DIR)
            logging.error(error_msg)
            raise Exception(error_msg)

        cls._start_emulator()

        for file in os.listdir(INSTRUMENTED_DIR):
            logging.info('Installing {0}'.format(file))
            cls._install_apk(os.path.join(INSTRUMENTED_DIR, file))

            if ("monkey" in tools):
                logcat_cmd = Command('adb', ['logcat', '-v', 'raw', '-s', 'hcai-intent-monitor', 'hcai-cg-monitor'])
                logcat_file = os.path.join(TRACE_DIR, "monkey", "{0}.logcat".format(file))

                with open(logcat_file, 'wb') as log_cat:
                    proc = logcat_cmd.invoke_as_deamon(stdout=log_cat)

                    logging.info('Executing {0}'.format(file))
                    start = time.time()

                    logging.info("Testing with monkey {0} seconds".format(int(timeout_by_apk)))
                    cls._exec_test_generator(file, timeout_by_apk)
                    
                    end = time.time()
                    logging.debug("Execution took {0} seconds".format(int(end-start)))
                    proc.kill()

                # logging.info('Uninstalling {0}'.format(file))
                # cls._uninstall_apk(os.path.join(INSTRUMENTED_DIR, file))

            if ("droidbot" in tools):
                logcat_cmd = Command('adb', ['logcat', '-v', 'raw', '-s', 'hcai-intent-monitor', 'hcai-cg-monitor'])
                logcat_file = os.path.join(TRACE_DIR, "droidbot", "{0}.logcat".format(file))

                with open(logcat_file, 'wb') as log_cat:
                    proc = logcat_cmd.invoke_as_deamon(stdout=log_cat)

                    logging.info('Executing {0}'.format(file))
                    start = time.time()
                    
                    logging.info("Testing with droidbot {0} seconds".format(int(timeout_by_apk)))
                    cls._exec_test_generator_droidbot(file, timeout_by_apk)

                    end = time.time()
                    logging.debug("Execution took {0} seconds".format(int(end-start)))
                    proc.kill()

            logging.info('Uninstalling {0}'.format(file))
            cls._uninstall_apk(os.path.join(INSTRUMENTED_DIR, file))

        cls._kill_emulator()

    @classmethod
    def phase_three_results(cls):
        logging.info('Droidfax\'s Phase 3: Results')

        # Collect instrumentation dependencies
        libs = list(map(lambda dep: os.path.join(LIBS_DIR, dep), os.listdir(LIBS_DIR)))
        main_cp = ':'.join(libs)

        # Collect soot dependencies
        droidfax_jar = os.path.join(LIBS_DIR, 'droidfax.jar')
        soot_cp = "{0}:{1}".format(droidfax_jar, ANDROID_JAR_PATH)

        # Create a folder to store droid results
        if os.path.exists(RESULTS_DIR):
            # Delete previous results
            logging.info('Removing previous results')
            shutil.rmtree(RESULTS_DIR)
        try:
            os.mkdir(RESULTS_DIR)
        except OSError:
            error_msg = 'Error while creating folder {0}'.format(RESULTS_DIR)
            logging.error(error_msg)
            raise Exception(error_msg)

        for file in os.listdir(INPUT_DIR):

            # Create file results folder.
            try:
                os.mkdir(os.path.join(RESULTS_DIR, file))
            except OSError:
                error_msg = 'Error while creating folder {0}'.format(os.path.join(RESULTS_DIR, file))
                logging.error(error_msg)
                raise Exception(error_msg)

            # General Results
            try:
                os.mkdir(os.path.join(RESULTS_DIR, file, 'general_report'))
            except OSError:
                error_msg = 'Error while creating folder {0}'.format(os.path.join(RESULTS_DIR, file, 'general_report'))
                logging.error(error_msg)
                raise Exception(error_msg)

            with open(os.path.join(RESULTS_DIR, file, 'general_report', 'general_report.log'), 'wb') as general_report_log:
                general_report_log.write('Result for {0}'.format(file).encode('ascii'))
                general_report_log.write(cls._get_package_name(os.path.join(INPUT_DIR, file)).encode('ascii'))

                general_report_cmd = Command('java', [
                    '-Xmx4g',
                    '-ea',
                    '-cp',
                    main_cp,
                    'reporters.generalReport',
                    '-w',
                    '-cp',
                    soot_cp,
                    '-p',
                    'cg',
                    'verbose:false,implicit-entry:true',
                    '-p',
                    'cg.spark',
                    'verbose:false,on-fly-cg:true,rta:false',
                    '-d',
                    os.path.join(TRACE_DIR, "{0}.logcat".format(file)),
                    '-process-dir',
                    os.path.join(INPUT_DIR, file),
                    '-trace',
                    os.path.join(TRACE_DIR, "{0}.logcat".format(file))
                ])
                general_report_cmd.invoke(stdout=general_report_log, stderr=general_report_log)

            for result_file in ['calleerank.txt', 'callerrank.txt', 'calleerankIns.txt', 'callerrankIns.txt', 'compdist.txt', 'edgefreq.txt', 'gdistcov.txt', 'gdistcovIns.txt', 'gfeatures.txt']:
                if os.path.exists(os.path.join(WORKING_DIR, result_file)):
                    os.rename(os.path.join(WORKING_DIR, result_file), os.path.join(RESULTS_DIR, file, 'general_report', result_file))

            # Security Results
            try:
                os.mkdir(os.path.join(RESULTS_DIR, file, 'security_report'))
            except OSError:
                error_msg = 'Error while creating folder {0}'.format(os.path.join(RESULTS_DIR, file, 'security_report'))
                logging.error(error_msg)
                raise Exception(error_msg)

            with open(os.path.join(RESULTS_DIR, file, 'security_report', 'security_report.log'), 'wb') as security_report_log:
                security_report_log.write('Result for {0}'.format(file).encode('ascii'))
                security_report_log.write(cls._get_package_name(os.path.join(INPUT_DIR, file)).encode('ascii'))

                security_report_cmd = Command('java', [
                    '-Xmx5g',
                    '-ea',
                    '-cp',
                    main_cp,
                    'reporters.rankReport',
                    '-w',
                    '-cp',
                    soot_cp,
                    '-p',
                    'cg',
                    'verbose:false,implicit-entry:true',
                    '-p',
                    'cg.spark',
                    'verbose:false,on-fly-cg:true,rta:false',
                    '-d',
                    os.path.join(TRACE_DIR, "{0}.logcat".format(file)),
                    '-catsrc',
                    os.path.join(WORKING_DIR, 'data', 'catsources.txt.final'),
                    '-catsink',
                    os.path.join(WORKING_DIR, 'data', 'catsinks.txt.final'),
                    '-catcallback',
                    os.path.join(WORKING_DIR, 'data', 'catCallbacks.txt'),
                    '-process-dir',
                    os.path.join(INPUT_DIR, file),
                    '-trace',
                    os.path.join(TRACE_DIR, "{0}.logcat".format(file))
                ])
                security_report_cmd.invoke(stdout=security_report_log, stderr=security_report_log)

            for result_file in ['srcsink.txt', 'src.txt', 'sink.txt', 'callback.txt', 'lifecycleMethod.txt', 'eventHandler.txt', 'securityfeatures.txt']:
                if os.path.exists(os.path.join(WORKING_DIR, result_file)):
                    os.rename(os.path.join(WORKING_DIR, result_file), os.path.join(RESULTS_DIR, file, 'security_report', result_file))

    @classmethod
    def _start_emulator(cls):
        logging.info('Starting emulator')
        start = time.time()
        
        start_emulator_cmd = Command('emulator', ['-avd', AVD_NAME, '-scale', '.3'])
        emulator_proc = start_emulator_cmd.invoke_as_deamon()

        logging.info('Waiting for emulator to boot')
        check_emulator_cmd = Command('adb', ['-s', 'emulator-5554', 'shell', 'getprop', 'init.svc.bootanim'])
        check_result = check_emulator_cmd.invoke()
        while check_result.stdout.strip().decode('ascii') != 'stopped':
            time.sleep(5)
            logging.info('Waiting for emulator to boot')
            check_result = check_emulator_cmd.invoke()

        logging.info('Emulator booted!')
        end = time.time()
        elapsed = end - start
        if elapsed > 60:
            logging.info('Emulator took {0} minutes and {1} seconds to boot'.format(int(elapsed / 60), elapsed % 60))
        else:
            logging.info('Emulator took {0} seconds to boot'.format(elapsed))
    
    @staticmethod
    def _kill_emulator():
        kill_emulator_cmd = Command('adb', ['-s', 'emulator-5554', 'emu', 'kill'])
        kill_emulator_cmd.invoke()
        kill_server_cmd = Command('adb', ['-s', 'emulator-5554', 'kill-server'])
        kill_server_cmd.invoke()

    @staticmethod
    def _install_apk(file):
        root_cmd = Command('adb', [
            'root',
        ])
        result = root_cmd.invoke()
        readlink_cmd = Command('greadlink', ['-f', file])
        readlink_result = readlink_cmd.invoke()
        install_cmd = Command('adb', [
            '-s',
            'emulator-5554',
            'install',
            '-r',
            readlink_result.stdout.strip().decode('ascii')
        ])
        install_cmd.invoke()

    @classmethod
    def _uninstall_apk(cls, file):
        package_name = cls._get_package_name(file)
        uninstall_cmd = Command('adb', ['-s', 'emulator-5554', 'uninstall', package_name])
        uninstall_cmd.invoke()

    # Start Droidbot:
    # droidbot -a <path_to_apk> -o output_dir
    @classmethod
    def _exec_test_generator_droidbot(cls, file, timeout):
        # package_name = cls._get_package_name(os.path.join(INSTRUMENTED_DIR, file))
        package_name = os.path.join('data', 'instrumented', file)
        droidbot_trace_file = os.path.join(TRACE_DIR, "droidbot", "{0}.droidbot".format(file))
        # logging.info(package_name)

        with open(droidbot_trace_file, 'wb') as droidbot_trace:
            exec_cmd = Command('droidbot', [
                '-d',
                'emulator-5554',
                '-a',
                package_name,
                '-timeout',
                str(timeout)
            ], timeout)
            exec_cmd.invoke(stdout=droidbot_trace)

        # Kill all droidbot process
        get_droidbot_processes_cmd = Command('adb', [
            'shell',
            'ps',
            '|',
            'grep',
            'com.android.commands.droidbot'
        ])
        get_droidbot_processes_result = get_droidbot_processes_cmd.invoke()
        for line in get_droidbot_processes_result.stdout.decode('ascii').split(os.linesep):
            if line.strip():
                tokens = line.split()
                kill_process_cmd = Command('adb', [
                    'shell',
                    'kill',
                    tokens[1],
                ])
                kill_process_cmd.invoke()

    @classmethod
    def _exec_test_generator(cls, file, timeout):
        package_name = cls._get_package_name(os.path.join(INSTRUMENTED_DIR, file))
        monkey_trace_file = os.path.join(TRACE_DIR, "monkey", "{0}.monkey".format(file))

        # Run monkey with timeout
        with open(monkey_trace_file, 'wb') as monkey_trace:
            exec_cmd = Command('adb', [
                'shell',
                'monkey',
                '-p',
                package_name,
                # '--ignore-crashes',
                # '--ignore-timeouts',
                '--ignore-security-exceptions',
                '100000'
            ], timeout)
            exec_cmd.invoke(stdout=monkey_trace)
        
        # Kill all monkey process
        get_monkey_processes_cmd = Command('adb', [
            'shell',
            'ps',
            '|',
            'grep',
            'com.android.commands.monkey'
        ])
        get_monkey_processes_result = get_monkey_processes_cmd.invoke()
        for line in get_monkey_processes_result.stdout.decode('ascii').split(os.linesep):
            if line.strip():
                tokens = line.split()
                kill_process_cmd = Command('adb', [
                    'shell',
                    'kill',
                    tokens[1],
                ])
                kill_process_cmd.invoke()

    @staticmethod
    def _get_package_name(file):
        readlink_cmd = Command('greadlink', ['-f', file])
        readlink_result = readlink_cmd.invoke()
        readlink_result_str = readlink_result.stdout.strip().decode('ascii')
        
        get_package_list_cmd = Command('aapt', ['list', '-a', file])
        get_package_list_result = get_package_list_cmd.invoke()
        get_package_list_result_str = get_package_list_result.stdout.strip().decode('ascii')

        match = re.search(r'Package Group .* packageCount=1 name=(.*)', get_package_list_result_str, re.MULTILINE)
        if match is None:
            match = re.search(r'package=(.*)', get_package_list_result_str, re.MULTILINE)
            if match is None:
                return None
        return match.group(1)