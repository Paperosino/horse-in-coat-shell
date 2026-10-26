#!/usr/bin/env bash
# Run only through SSH inside the disposable CachyOS live VM. Never on the host.
set -euo pipefail
[[ ${1:-} == --disposable-cachyos-vm ]] || { echo 'Explicit VM-only argument required' >&2; exit 2; }
[[ $(id -u) == 0 ]]
[[ $(cat /sys/class/dmi/id/sys_vendor) == QEMU ]]
[[ -e /run/archiso/bootmnt/arch/x86_64/airootfs.sfs ]]
[[ $(blockdev --getsize64 /dev/vda) == 64424509440 ]]
[[ $(lsblk -ndo RO /dev/vda) == 0 ]]
[[ $(lsblk -nr -o NAME /dev/vda | wc -l) == 1 ]] || { echo 'Test disk is already partitioned; refusing to overwrite it' >&2; exit 2; }
. /etc/os-release
[[ $ID == cachyos && ${IMAGE_VERSION:-} == 2026.08.09 ]]
printf 'Verified disposable CachyOS VM; installing only onto its empty 60 GiB vda\n'
sgdisk --clear --new=1:0:+512M --typecode=1:ef00 --change-name=1:HICS_TEST_ESP --new=2:0:0 --typecode=2:8300 --change-name=2:HICS_TEST_ROOT /dev/vda
udevadm settle
mkfs.fat -F32 -n HICS_ESP /dev/vda1
mkfs.btrfs -f -L HICS_TEST_ROOT /dev/vda2
mount /dev/vda2 /mnt
btrfs subvolume create /mnt/@
btrfs subvolume create /mnt/@home
umount /mnt
mount -o subvol=@,compress=zstd:1 /dev/vda2 /mnt
mkdir -p /mnt/home /mnt/boot/efi
mount -o subvol=@home,compress=zstd:1 /dev/vda2 /mnt/home
mount /dev/vda1 /mnt/boot/efi
pacman -Sy --noconfirm archlinux-keyring cachyos-keyring
pacstrap -K /mnt base linux-cachyos linux-firmware networkmanager sudo openssh grub efibootmgr btrfs-progs cachyos-keyring cachyos-mirrorlist cachyos-v3-mirrorlist cachyos-hooks cachyos-settings
cp /etc/pacman.conf /mnt/etc/pacman.conf
genfstab -U /mnt > /mnt/etc/fstab
sed -i -e 's/^#en_US.UTF-8/en_US.UTF-8/' -e 's/^#ru_RU.UTF-8/ru_RU.UTF-8/' /mnt/etc/locale.gen
arch-chroot /mnt locale-gen
printf 'LANG=ru_RU.UTF-8\n' > /mnt/etc/locale.conf
printf 'hics-test\n' > /mnt/etc/hostname
arch-chroot /mnt ln -sf /usr/share/zoneinfo/Europe/Moscow /etc/localtime
arch-chroot /mnt useradd -m -G wheel -s /bin/bash hics-test
# Random, undisclosed root password unlocks public-key login; never log it.
{ printf 'root:'; openssl rand -base64 32; } | arch-chroot /mnt chpasswd
install -d -m700 /mnt/root/.ssh
install -m600 /root/.ssh/authorized_keys /mnt/root/.ssh/authorized_keys
arch-chroot /mnt grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=HICS_TEST --removable
arch-chroot /mnt grub-mkconfig -o /boot/grub/grub.cfg
systemctl --root=/mnt enable NetworkManager sshd fstrim.timer
mkdir -p /mnt/var/lib/hics-lab
printf '{"stage":"base-installed","origin":"CachyOS official 260809 live ISO","method":"guarded pacstrap into disposable VM"}\n' > /mnt/var/lib/hics-lab/base-ready.json
sync
printf 'HICS_CACHYOS_BASE_INSTALLED\n'
