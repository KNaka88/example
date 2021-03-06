# Copyright 2014 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Command for creating images."""

from googlecloudsdk.api_lib.compute import base_classes
from googlecloudsdk.api_lib.compute import csek_utils
from googlecloudsdk.api_lib.compute import image_utils
from googlecloudsdk.api_lib.compute import utils
from googlecloudsdk.calliope import arg_parsers
from googlecloudsdk.calliope import base
from googlecloudsdk.calliope import exceptions
from googlecloudsdk.command_lib.compute import flags as compute_flags
from googlecloudsdk.command_lib.compute.images import flags
from googlecloudsdk.command_lib.util import labels_util


@base.ReleaseTracks(base.ReleaseTrack.GA)
class Create(base.CreateCommand):
  """Create Google Compute Engine images."""

  _ALLOW_RSA_ENCRYPTED_CSEK_KEYS = False

  _GUEST_OS_FEATURES = image_utils.GUEST_OS_FEATURES

  @classmethod
  def Args(cls, parser):
    parser.display_info.AddFormat(flags.LIST_FORMAT)
    parser.add_argument(
        '--description',
        help=('An optional, textual description for the image being created.'))

    parser.add_argument(
        '--source-uri',
        help="""\
        The full Google Cloud Storage URI where the disk image is stored.
        This file must be a gzip-compressed tarball whose name ends in
        ``.tar.gz''.

        This flag is mutually exclusive with ``--source-disk''.
        """)

    flags.SOURCE_DISK_ARG.AddArgument(parser)
    parser.add_argument(
        '--family',
        help=('The family of the image. When creating an instance or disk, '
              'specifying a family will cause the latest non-deprecated image '
              'in the family to be used.')
    )

    parser.add_argument(
        '--licenses',
        type=arg_parsers.ArgList(),
        help='Comma-separated list of URIs to license resources.')

    if cls._GUEST_OS_FEATURES:
      parser.add_argument(
          '--guest-os-features',
          metavar='GUEST_OS_FEATURE',
          type=arg_parsers.ArgList(element_type=lambda x: x.upper(),
                                   choices=cls._GUEST_OS_FEATURES),
          help=('One or more features supported by the OS in the image.'))

    Create.DISK_IMAGE_ARG = flags.MakeDiskImageArg()
    Create.DISK_IMAGE_ARG.AddArgument(parser, operation_type='create')
    csek_utils.AddCsekKeyArgs(parser, resource_type='image')

  def Run(self, args):
    """Returns a list of requests necessary for adding images."""
    holder = base_classes.ComputeApiHolder(self.ReleaseTrack())
    client = holder.client
    messages = client.messages

    image_ref = Create.DISK_IMAGE_ARG.ResolveAsResource(args, holder.resources)
    image = messages.Image(
        name=image_ref.image,
        description=args.description,
        sourceType=messages.Image.SourceTypeValueValuesEnum.RAW,
        family=args.family)

    csek_keys = csek_utils.CsekKeyStore.FromArgs(
        args, self._ALLOW_RSA_ENCRYPTED_CSEK_KEYS)
    if csek_keys:
      image.imageEncryptionKey = csek_utils.MaybeToMessage(
          csek_keys.LookupKey(image_ref,
                              raise_if_missing=args.require_csek_key_create),
          client.apitools_client)

    # Validate parameters.
    if args.source_disk_zone and not args.source_disk:
      raise exceptions.ToolException(
          'You cannot specify [--source-disk-zone] unless you are specifying '
          '[--source-disk].')

    if args.source_disk and args.source_uri:
      raise exceptions.ConflictingArgumentsException(
          '--source-uri', '--source-disk')

    if not (args.source_disk or args.source_uri):
      raise exceptions.MinimumArgumentException(
          ['--source-uri', '--source-disk'],
          'Please specify either the source disk or the Google Cloud Storage '
          'URI of the disk image.'
      )

    # TODO(b/30086260): use resources.REGISTRY.Parse() for GCS URIs.
    if args.source_uri:
      source_uri = utils.NormalizeGoogleStorageUri(args.source_uri)
      image.rawDisk = messages.Image.RawDiskValue(source=source_uri)
    else:
      source_disk_ref = flags.SOURCE_DISK_ARG.ResolveAsResource(
          args, holder.resources,
          scope_lister=compute_flags.GetDefaultScopeLister(client))
      image.sourceDisk = source_disk_ref.SelfLink()
      image.sourceDiskEncryptionKey = csek_utils.MaybeLookupKeyMessage(
          csek_keys, source_disk_ref, client.apitools_client)

    if args.licenses:
      image.licenses = args.licenses

    guest_os_features = getattr(args, 'guest_os_features', [])
    if guest_os_features:
      guest_os_feature_messages = []
      for feature in guest_os_features:
        gf_type = messages.GuestOsFeature.TypeValueValuesEnum(feature)
        guest_os_feature = messages.GuestOsFeature()
        guest_os_feature.type = gf_type
        guest_os_feature_messages.append(guest_os_feature)
      image.guestOsFeatures = guest_os_feature_messages

    request = messages.ComputeImagesInsertRequest(
        image=image,
        project=image_ref.project)

    args_labels = getattr(args, 'labels', None)
    if args_labels:
      labels = messages.Image.LabelsValue(additionalProperties=[
          messages.Image.LabelsValue.AdditionalProperty(
              key=key, value=value)
          for key, value in sorted(args_labels.iteritems())])
      request.image.labels = labels

    return client.MakeRequests([(client.apitools_client.images, 'Insert',
                                 request)])


@base.ReleaseTracks(base.ReleaseTrack.BETA)
class CreateBeta(Create):

  # Used in CreateRequests. We only want to allow RSA key wrapping in
  # alpha/beta, *not* GA.
  _ALLOW_RSA_ENCRYPTED_CSEK_KEYS = True

  _GUEST_OS_FEATURES = image_utils.GUEST_OS_FEATURES_BETA

  @classmethod
  def Args(cls, parser):
    super(CreateBeta, cls).Args(parser)
    labels_util.AddCreateLabelsFlags(parser)


@base.ReleaseTracks(base.ReleaseTrack.ALPHA)
class CreateAlpha(CreateBeta):

  _GUEST_OS_FEATURES = image_utils.GUEST_OS_FEATURES_ALPHA


Create.detailed_help = {
    'brief': 'Create Google Compute Engine images',
    'DESCRIPTION': """\
        *{command}* is used to create custom disk images.
        The resulting image can be provided during instance or disk creation
        so that the instance attached to the resulting disks has access
        to a known set of software or files from the image.

        Images can be created from gzipped compressed tarball containing raw
        disk data or from existing disks in any zone.

        Images are global resources, so they can be used across zones and
        projects.

        To learn more about creating image tarballs, visit
        [](https://cloud.google.com/compute/docs/creating-custom-image)
        """,
}

CreateBeta.detailed_help = Create.detailed_help
CreateAlpha.detailed_help = Create.detailed_help
