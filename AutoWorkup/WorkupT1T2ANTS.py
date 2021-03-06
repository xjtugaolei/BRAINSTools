#!/usr/bin/env python

from nipype.interfaces.base import CommandLine, CommandLineInputSpec, TraitedSpec, File, Directory
from nipype.interfaces.base import traits, isdefined, BaseInterface
from nipype.interfaces.utility import Merge, Split, Function, Rename, IdentityInterface
import nipype.interfaces.io as nio   # Data i/o
import nipype.pipeline.engine as pe  # pypeline engine

import os

from SEMTools import *

"""
    from WorkupT1T2ANTS import CreateANTSRegistrationWorkflow
    myLocalAntsWF = CreateANTSRegistrationWorkflow("ANTSRegistration",CLUSTER_QUEUE)
    ANTSWF.connect( SplitAvgBABC,'avgBABCT1',myLocalAntsWF,"inputspec.fixedVolumesList")
    ANTSWF.connect( BAtlas,'template_t1',    myLocalAntsWF,"inputspec.movingVolumesList")
    ANTSWF.connect(myLocalLMIWF,'outputspec.atlasToSubjectTransform',myLocalAntsWF,'inputspec.initial_moving_transform')
"""


def CreateANTSRegistrationWorkflow(WFname, CLUSTER_QUEUE, CLUSTER_QUEUE_LONG, NumberOfThreads=-1):
    ANTSWF = pe.Workflow(name=WFname)

    inputsSpec = pe.Node(interface=IdentityInterface(fields=['fixedVolumesList', 'movingVolumesList', 'initial_moving_transform',
                                                             'fixedBinaryVolume', 'movingBinaryVolume', 'warpFixedVolumesList'
                                                             ]), name='inputspec')

    print("""Run ANTS Registration""")

    BFitAtlasToSubject = pe.Node(interface=BRAINSFit(), name="bfA2S")
    BF_cpu_sge_options_dictionary = {'qsub_args': '-S /bin/bash -pe smp1 2-12 -l h_vmem=14G,mem_free=4G -o /dev/null -e /dev/null ' + CLUSTER_QUEUE, 'overwrite': True}
    BFitAtlasToSubject.plugin_args = BF_cpu_sge_options_dictionary
    BFitAtlasToSubject.inputs.costMetric = "MMI"
    BFitAtlasToSubject.inputs.numberOfSamples = 1000000
    BFitAtlasToSubject.inputs.numberOfIterations = [1500]
    BFitAtlasToSubject.inputs.numberOfHistogramBins = 50
    BFitAtlasToSubject.inputs.maximumStepLength = 0.2
    BFitAtlasToSubject.inputs.minimumStepLength = [0.000005]
    BFitAtlasToSubject.inputs.useAffine = True  # Using initial transform from BRAINSABC
    BFitAtlasToSubject.inputs.maskInferiorCutOffFromCenter = 65
    BFitAtlasToSubject.inputs.outputVolume = "Trial_Initializer_Output.nii.gz"
    # Bug in BRAINSFit PREDICTIMG-1379 BFitAtlasToSubject.inputs.outputFixedVolumeROI="FixedROI.nii.gz"
    # Bug in BRAINSFit PREDICTIMG-1379 BFitAtlasToSubject.inputs.outputMovingVolumeROI="MovingROI.nii.gz"
    BFitAtlasToSubject.inputs.outputTransform = "Trial_Initializer_Output.h5"
    BFitAtlasToSubject.inputs.maskProcessingMode = "ROIAUTO"
    BFitAtlasToSubject.inputs.ROIAutoDilateSize = 4
    # BFitAtlasToSubject.inputs.maskProcessingMode="ROI"
   # ANTSWF.connect(inputsSpec,'fixedBinaryVolume',BFitAtlasToSubject,'fixedBinaryVolume')
   # ANTSWF.connect(inputsSpec,'movingBinaryVolume',BFitAtlasToSubject,'movingBinaryVolume')
    ANTSWF.connect(inputsSpec, 'fixedVolumesList', BFitAtlasToSubject, 'fixedVolume')
    ANTSWF.connect(inputsSpec, 'movingVolumesList', BFitAtlasToSubject, 'movingVolume')
    ANTSWF.connect(inputsSpec, 'initial_moving_transform', BFitAtlasToSubject, 'initialTransform')

    ComputeAtlasToSubjectTransform = pe.Node(interface=antsRegistration(), name="antsA2S")
    many_cpu_sge_options_dictionary = {'qsub_args': '-S /bin/bash -pe smp1 5-12 -l h_vmem=17G,mem_free=9G -o /dev/null -e /dev/null ' + CLUSTER_QUEUE, 'overwrite': True}
    ComputeAtlasToSubjectTransform.plugin_args = many_cpu_sge_options_dictionary

    ComputeAtlasToSubjectTransform.inputs.dimension = 3
    ComputeAtlasToSubjectTransform.inputs.metric = 'CC'  # This is a family of interfaces, CC,MeanSquares,Demons,GC,MI,Mattes
    ComputeAtlasToSubjectTransform.inputs.transform = 'SyN[0.25,3.0,0.0]'
    ComputeAtlasToSubjectTransform.inputs.number_of_iterations = [250, 100, 20]
    ComputeAtlasToSubjectTransform.inputs.convergence_threshold = 1e-7
    ComputeAtlasToSubjectTransform.inputs.smoothing_sigmas = [0, 0, 0]
    ComputeAtlasToSubjectTransform.inputs.sigma_units = ["vox"]
    ComputeAtlasToSubjectTransform.inputs.shrink_factors = [3, 2, 1]
    ComputeAtlasToSubjectTransform.inputs.use_estimate_learning_rate_once = True
    ComputeAtlasToSubjectTransform.inputs.use_histogram_matching = True
    ComputeAtlasToSubjectTransform.inputs.invert_initial_moving_transform = False
    ComputeAtlasToSubjectTransform.inputs.output_transform_prefix = 'antsRegPrefix_'
    ComputeAtlasToSubjectTransform.inputs.output_warped_image = 'moving_to_fixed.nii.gz'
    ComputeAtlasToSubjectTransform.inputs.output_inverse_warped_image = 'fixed_to_moving.nii.gz'
    # ComputeAtlasToSubjectTransform.inputs.num_threads=-1
    # if os.environ.has_key('NSLOTS'):
    #    ComputeAtlasToSubjectTransform.inputs.num_threads=int(os.environ.has_key('NSLOTS'))
    # else:
    #    ComputeAtlasToSubjectTransform.inputs.num_threads=NumberOfThreads
    # ComputeAtlasToSubjectTransform.inputs.fixedMask=SUBJ_A_small_T2_mask.nii.gz
    # ComputeAtlasToSubjectTransform.inputs.movingMask=SUBJ_B_small_T2_mask.nii.gz

    ANTSWF.connect(inputsSpec, 'fixedVolumesList', ComputeAtlasToSubjectTransform, "fixed_image")
    ANTSWF.connect(inputsSpec, 'movingVolumesList', ComputeAtlasToSubjectTransform, "moving_image")
    ANTSWF.connect(BFitAtlasToSubject, 'outputTransform', ComputeAtlasToSubjectTransform, 'initial_moving_transform')

    if 1 == 1:
        mergeAffineWarp = pe.Node(interface=Merge(2), name="Merge_AffineWarp")
        ANTSWF.connect(ComputeAtlasToSubjectTransform, 'warp_transform', mergeAffineWarp, 'in1')
        ANTSWF.connect(BFitAtlasToSubject, 'outputTransform', mergeAffineWarp, 'in2')

        from nipype.interfaces.ants import WarpImageMultiTransform
        debugWarpTest = pe.Node(interface=WarpImageMultiTransform(), name="dbgWarpTest")
        # Not allowed as an input debugWarpTest.inputs.output_image = 'debugWarpedMovingToFixed.nii.gz'

        ANTSWF.connect(inputsSpec, 'fixedVolumesList', debugWarpTest, 'reference_image')
        ANTSWF.connect(inputsSpec, 'movingVolumesList', debugWarpTest, 'moving_image')
        ANTSWF.connect(mergeAffineWarp, 'out', debugWarpTest, 'transformation_series')

    #############
    outputsSpec = pe.Node(interface=IdentityInterface(fields=['warped_image', 'inverse_warped_image', 'warp_transform',
                                                              'inverse_warp_transform', 'affine_transform'
                                                              ]), name='outputspec')

    ANTSWF.connect(ComputeAtlasToSubjectTransform, 'warped_image', outputsSpec, 'warped_image')
    ANTSWF.connect(ComputeAtlasToSubjectTransform, 'inverse_warped_image', outputsSpec, 'inverse_warped_image')
    ANTSWF.connect(ComputeAtlasToSubjectTransform, 'warp_transform', outputsSpec, 'warp_transform')
    ANTSWF.connect(ComputeAtlasToSubjectTransform, 'inverse_warp_transform', outputsSpec, 'inverse_warp_transform')
    ANTSWF.connect(BFitAtlasToSubject, 'outputTransform', outputsSpec, 'affine_transform')

    return ANTSWF
