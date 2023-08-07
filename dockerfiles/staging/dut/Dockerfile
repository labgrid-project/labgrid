FROM debian:bookworm-slim

MAINTAINER "Kasper Revsbech" <mail@krevsbech.dk>

ENV DEBIAN_FRONTEND=noninteractive

RUN set -e ;\
    apt update -q=2 ;\
    apt install -q=2 --yes --no-install-recommends openssh-server;\
    apt clean ;\
    rm -rf /var/lib/apt/lists/* ;\
    mkdir /var/run/sshd ;\
    echo 'root:PASSWORD' | chpasswd ;\
    echo 'PermitRootLogin yes' >> /etc/ssh/sshd_config ;\
    sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd
    # SSH login fix. Otherwise user is kicked off after login

COPY --chown=root:root ./authorized_keys /root/.ssh/authorized_keys

# As sshd scrubs ENV variables if they are set by the ENV varibale ensure to put the into /etc/profile as shown below
ENV NOTVISIBLE "in users profile"
RUN echo "export VISIBLE=now" >> /etc/profile

EXPOSE 2222
CMD ["/usr/sbin/sshd", "-D", "-p", "2222"]
